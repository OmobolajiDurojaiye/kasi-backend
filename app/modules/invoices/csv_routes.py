from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.csv_service import CsvService

csv_bp = Blueprint('csv', __name__)

@csv_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_csv():
    current_user_id = get_jwt_identity()
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file:
        result = CsvService.process_csv(current_user_id, file)
        return jsonify(result), 200
        
    return jsonify({"error": "Upload failed"}), 500
