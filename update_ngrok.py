import requests
import sys
import os

def update_webhook():
    # 1. Fetch the active ngrok tunnel URL
    try:
        resp = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=2)
        tunnels = resp.json().get('tunnels', [])
        public_url = None
        for t in tunnels:
            if t.get('proto') == 'https':
                public_url = t['public_url']
                break
        
        if not public_url and tunnels:
            public_url = tunnels[0]['public_url']
            
        if not public_url:
            print("ERROR: No active ngrok tunnels found. Is ngrok running?")
            sys.exit(1)
            
        print(f"SUCCESS: Found active ngrok tunnel: {public_url}")
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to ngrok API at port 4040. Is ngrok running?")
        sys.exit(1)

    # 2. Get the bot token from the DB (we need the flask context)
    # We add the app source to path to import it cleanly
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from app import create_app
    from app.modules.telegram.models import TelegramBot
    
    app = create_app()
    with app.app_context():
        bots = TelegramBot.query.filter_by(is_active=True).all()
        if not bots:
            print("ERROR: No active Telegram bots found in the database.")
            sys.exit(1)
            
        for bot in bots:
            webhook_url = f"{public_url}/api/telegram/webhook/{bot.user_id}"
            
            # 3. Call Telegram API to update the webhook
            tg_url = f"https://api.telegram.org/bot{bot.bot_token}/setWebhook"
            payload = {"url": webhook_url}
            
            try:
                tg_resp = requests.post(tg_url, json=payload)
                if tg_resp.json().get('ok'):
                    print(f"SUCCESS: Updated Webhook for User #{bot.user_id} to: {webhook_url}")
                else:
                    print(f"ERROR: Failed to set webhook for User #{bot.user_id}: {tg_resp.text}")
            except Exception as e:
                print(f"ERROR: Communicating with Telegram API: {e}")

if __name__ == "__main__":
    update_webhook()
