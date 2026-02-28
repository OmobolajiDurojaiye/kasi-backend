import os
import requests
from app.modules.telegram.models import TelegramBot
from app.services.sales_ai import SalesAI

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramService:

    @staticmethod
    def verify_token(token):
        """Verify a bot token by calling Telegram's getMe endpoint."""
        try:
            resp = requests.get(f"{TELEGRAM_API.format(token=token)}/getMe", timeout=10)
            data = resp.json()
            if data.get('ok'):
                return {
                    'valid': True,
                    'username': data['result'].get('username'),
                    'first_name': data['result'].get('first_name'),
                }
            return {'valid': False, 'error': data.get('description', 'Invalid token')}
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    @staticmethod
    def set_webhook(token, webhook_url):
        """Set the Telegram webhook URL for the bot."""
        try:
            resp = requests.post(
                f"{TELEGRAM_API.format(token=token)}/setWebhook",
                json={"url": webhook_url},
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            return {'ok': False, 'description': str(e)}

    @staticmethod
    def delete_webhook(token):
        """Remove the webhook."""
        try:
            resp = requests.post(
                f"{TELEGRAM_API.format(token=token)}/deleteWebhook",
                timeout=10,
            )
            return resp.json()
        except Exception as e:
            return {'ok': False, 'description': str(e)}

    @staticmethod
    def send_message(token, chat_id, text, parse_mode='Markdown'):
        """Send a message via Telegram Bot API."""
        try:
            requests.post(
                f"{TELEGRAM_API.format(token=token)}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
                timeout=10,
            )
        except Exception as e:
            print(f"Telegram send error: {e}")

    @staticmethod
    def send_document(token, chat_id, filepath, caption=''):
        """Send a PDF/document file via Telegram Bot API."""
        try:
            abs_path = filepath
            if not os.path.isabs(filepath):
                from flask import current_app
                abs_path = os.path.join(current_app.root_path, filepath.lstrip('/'))

            if not os.path.exists(abs_path):
                print(f"Telegram send_document: file not found: {abs_path}")
                return

            with open(abs_path, 'rb') as f:
                requests.post(
                    f"{TELEGRAM_API.format(token=token)}/sendDocument",
                    data={
                        "chat_id": chat_id,
                        "caption": caption,
                        "parse_mode": "Markdown",
                    },
                    files={"document": (os.path.basename(abs_path), f, 'application/pdf')},
                    timeout=30,
                )
        except Exception as e:
            print(f"Telegram send_document error: {e}")

    @staticmethod
    def process_incoming(user_id, text, chat_id, sender_name='Telegram Customer'):
        """
        Process an incoming Telegram message.
        Delegates to the unified SalesAI engine.
        Returns a string (text reply) or a dict with 'text' and optional 'pdf_path'.
        """
        return SalesAI.process(user_id, text, 'telegram', sender_name, customer_id=chat_id)
