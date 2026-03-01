import requests as http_requests
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from .models import TelegramBot
from ...services.telegram_service import TelegramService

telegram_bp = Blueprint('telegram', __name__)


def _get_public_url():
    """Try to get the ngrok public HTTPS URL, fall back to request.host_url."""
    try:
        resp = http_requests.get('http://127.0.0.1:4040/api/tunnels', timeout=2)
        tunnels = resp.json().get('tunnels', [])
        for t in tunnels:
            if t.get('proto') == 'https':
                return t['public_url']
        if tunnels:
            return tunnels[0]['public_url']
    except Exception:
        pass
    return request.host_url.rstrip('/')


# ── Connect: verify token, save, set webhook ──────────
@telegram_bp.route('/connect', methods=['POST'])
@jwt_required()
def connect():
    user_id = get_jwt_identity()
    data = request.get_json()
    token = data.get('bot_token', '').strip()

    if not token:
        return jsonify({"error": "Bot token is required"}), 400

    # Verify token with Telegram
    verify = TelegramService.verify_token(token)
    if not verify['valid']:
        return jsonify({"error": f"Invalid token: {verify.get('error', 'unknown')}"}), 400

    bot_username = verify.get('username', '')

    # Auto-detect ngrok public URL for the webhook
    base_url = _get_public_url()
    webhook_url = f"{base_url}/api/telegram/webhook/{user_id}"

    result = TelegramService.set_webhook(token, webhook_url)
    if not result.get('ok'):
        # Webhook setting failed — still save the bot but mark inactive
        pass

    # Save or update bot record
    bot = TelegramBot.query.filter_by(user_id=user_id).first()
    if bot:
        bot.bot_token = token
        bot.bot_username = bot_username
        bot.is_active = True
    else:
        bot = TelegramBot(
            user_id=user_id,
            bot_token=token,
            bot_username=bot_username,
            is_active=True,
        )
        db.session.add(bot)

    db.session.commit()

    return jsonify({
        "message": "Telegram bot connected!",
        "bot": bot.to_dict(),
        "webhook_url": webhook_url,
    }), 200


# ── Disconnect ────────────────────────────────────────
@telegram_bp.route('/disconnect', methods=['DELETE'])
@jwt_required()
def disconnect():
    user_id = get_jwt_identity()
    bot = TelegramBot.query.filter_by(user_id=user_id).first()
    if not bot:
        return jsonify({"error": "No bot connected"}), 404

    TelegramService.delete_webhook(bot.bot_token)
    db.session.delete(bot)
    db.session.commit()

    return jsonify({"message": "Bot disconnected"}), 200


# ── Status ────────────────────────────────────────────
@telegram_bp.route('/status', methods=['GET'])
@jwt_required()
def status():
    user_id = get_jwt_identity()
    bot = TelegramBot.query.filter_by(user_id=user_id).first()
    if not bot:
        return jsonify({"connected": False}), 200
    return jsonify({"connected": True, "bot": bot.to_dict()}), 200


# ── Incoming webhook (PUBLIC — no JWT) ────────────────
@telegram_bp.route('/webhook/<int:user_id>', methods=['POST'])
def incoming_webhook(user_id):
    """Receives Telegram updates for a specific user's bot."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": True}), 200

    # Extract message text or caption (for images like receipts)
    message = data.get('message', {})
    text = message.get('text') or message.get('caption', '')
    chat_id = message.get('chat', {}).get('id')
    sender = message.get('from', {})
    sender_name = f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip() or 'Telegram Customer'

    if not text or not chat_id:
        return jsonify({"ok": True}), 200

    # Look up the bot to get the token
    bot = TelegramBot.query.filter_by(user_id=user_id, is_active=True).first()
    if not bot:
        return jsonify({"ok": True}), 200

    # Process the message
    result = TelegramService.process_incoming(user_id, text, chat_id, sender_name)

    # SalesAI returns a dict for orders (with PDF), string for everything else
    if isinstance(result, dict):
        # Send text reply
        TelegramService.send_message(bot.bot_token, chat_id, result['text'])

        # Send PDF invoice as document
        if result.get('pdf_path'):
            TelegramService.send_document(
                bot.bot_token,
                chat_id,
                result['pdf_path'],
                caption=f"📄 Invoice for your order"
            )
    else:
        # Simple text reply
        TelegramService.send_message(bot.bot_token, chat_id, result)

    return jsonify({"ok": True}), 200
