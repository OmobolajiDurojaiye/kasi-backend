from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...services.webhook_service import WebhookService

webhook_bp = Blueprint('webhooks', __name__)

@webhook_bp.route('/simulate', methods=['POST'])
@jwt_required()
def simulate_webhook():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    text = data.get('text', '')
    platform = data.get('platform', 'whatsapp')
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    response = WebhookService.process_simulation(current_user_id, text, platform)
    
    return jsonify(response), 200
