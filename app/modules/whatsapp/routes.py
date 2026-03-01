from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import requests
import os
from app.extensions import db
from app.modules.auth.models import User, Integration
from app.services.sales_ai import SalesAI

whatsapp_bp = Blueprint('whatsapp', __name__)

# NOTE: Since Evolution API will be hosted externally (e.g. Railway),
# you will configure these via env vars in PythonAnywhere later.
EVOLUTION_API_URL = os.environ.get('EVOLUTION_API_URL', 'http://localhost:8080')
EVOLUTION_GLOBAL_API_KEY = os.environ.get('EVOLUTION_GLOBAL_API_KEY', 'default_secret')

@whatsapp_bp.route('/connect', methods=['POST'])
@jwt_required()
def connect_whatsapp():
    """
    Generates a new Evolution API Instance for the Kasi Merchant,
    saves the pairing to the Integration DB table, and returns the QR code.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404

    # The unique ID Evolution will use to identify this merchant's phone
    instance_name = f"kasi_user_{user_id}"

    # 1. Check if an integration already exists for this user
    integration = Integration.query.filter_by(user_id=user_id, platform='whatsapp').first()
    if not integration:
        integration = Integration(
            user_id=user_id,
            platform='whatsapp',
            instance_name=instance_name,
            connection_status='pending'
        )
        db.session.add(integration)
        db.session.commit()

    # 2. Call Evolution API to Generate Instance + QR
    # Currently stubbed out to avoid crashing if Evolution isn't running locally yet.
    # When Evolution is live, uncomment the requests.post below.
    try:
        """
        payload = {
            "instanceName": instance_name,
            "token": f"kasi_{user_id}_secure",
            "qrcode": True,
            # Point this back to your live PythonAnywhere URL
            "webhook": "https://your_kasi_domain.com/api/whatsapp/webhook",
            "events": ["MESSAGES_UPSERT"] # We only care about new text messages
        }
        headers = {"apikey": EVOLUTION_GLOBAL_API_KEY}
        response = requests.post(f"{EVOLUTION_API_URL}/instance/create", json=payload, headers=headers)
        
        if response.status_code == 201:
            qr_base64 = response.json().get('qrcode', {}).get('base64')
            return jsonify({"status": "success", "qr_code": qr_base64}), 200
        else:
            return jsonify({"error": "Failed to generate QR code from Evolution"}), 500
        """
        
        # Stub response for MVP testing
        return jsonify({
            "status": "stubbed",
            "message": "When Evolution API is live, this will return a base64 QR Code string for the frontend to render.",
            "instance_name": instance_name
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@whatsapp_bp.route('/webhook', methods=['POST'])
def whatsapp_webhook():
    """
    Receives incoming WhatsApp messages from the Evolution API server, 
    routes them to the AI, and replies.
    """
    data = request.json
    
    # Check if this is a standard message upsert event
    event = data.get('event')
    if event != 'messages.upsert':
        return "Ignored", 200

    # 1. Identify which Merchant received the message
    instance_name = data.get('instance')
    integration = Integration.query.filter_by(instance_name=instance_name, platform='whatsapp').first()
    
    if not integration:
        print(f"[WhatsApp] Unknown instance: {instance_name}")
        return "Unknown Instance", 404

    merchant = integration.user

    # 2. Extract Message details
    message_data = data.get('data', {}).get('message', {})
    
    # customer_phone looks like '2348012345678@s.whatsapp.net'
    customer_phone = data.get('data', {}).get('key', {}).get('remoteJid') 
    
    # We only care about normal text messages for now
    incoming_text = message_data.get('conversation') or message_data.get('extendedTextMessage', {}).get('text')
    
    # Ignore "System" messages or statuses
    if not incoming_text or "status@broadcast" in customer_phone:
        return "Not a text message", 200
    
    # Extract just the digits from the JID (optional, but good for DB)
    customer_number_cleaned = customer_phone.split('@')[0]

    # 3. Process via AI Kitchen
    try:
        # Same engine used for Telegram!
        ai_response = SalesAI.process(
            user_id=merchant.id,
            text=incoming_text,
            platform='whatsapp',
            sender_name=f"Customer wa_{customer_number_cleaned}",
            customer_id=f"wa_{customer_number_cleaned}"
        )

        # 4. Sent reply back out to Evolution API
        """
        send_payload = {
            "number": customer_phone,
            "text": ai_response
        }
        requests.post(
            f"{EVOLUTION_API_URL}/message/sendText/{instance_name}",
            json=send_payload,
            headers={"apikey": EVOLUTION_GLOBAL_API_KEY}
        )
        """
        print(f"[WhatsApp Stub] AI Reply generated: {ai_response}")
        
    except Exception as e:
        print(f"[WhatsApp Webhook Error] {e}")

    return "OK", 200
