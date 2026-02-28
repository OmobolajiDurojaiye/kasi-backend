from flask import Blueprint, request, jsonify
from app.extensions import db, jwt
from .models import User
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"message": "Email already registered"}), 400
        
    user = User(
        business_name=data['business_name'],
        email=data['email']
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({"message": "User registered successfully"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if user and user.check_password(data['password']):
        if getattr(user, 'account_status', 'active') != 'active':
            return jsonify({"message": f"Account is {user.account_status}. Please contact support."}), 403
            
        access_token = create_access_token(identity=str(user.id))
        return jsonify({
            "access_token": access_token,
            "user": user.to_dict()
        }), 200
        
    return jsonify({"message": "Invalid credentials"}), 401

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"message": "User not found"}), 404
        
    if getattr(user, 'account_status', 'active') != 'active':
        return jsonify({"message": f"Account is {user.account_status}."}), 403
        
    return jsonify(user.to_dict()), 200

@auth_bp.route('/profile', methods=['PATCH'])
@jwt_required()
def update_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    data = request.get_json()
    
    # Update fields if provided
    if 'business_name' in data:
        user.business_name = data['business_name']
    if 'phone' in data:
        user.phone = data['phone']
    if 'address' in data:
        user.address = data['address']
    if 'logo_url' in data:
        user.logo_url = data['logo_url']
    if 'bank_name' in data:
        user.bank_name = data['bank_name']
    if 'account_number' in data:
        user.account_number = data['account_number']
    if 'account_name' in data:
        user.account_name = data['account_name']
        
    db.session.commit()
    return jsonify(user.to_dict()), 200

import os
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename
from flask import current_app, url_for

# Configure Cloudinary (Should ideally be in extensions or app factory, but here is fine for MVP speed)
# We need to access app config, so we do it inside the function or rely on env vars if lib supports it.
# cloudinary.config(cloud_name=..., api_key=..., api_secret=...) handles env vars automatically if CLOUDINARY_URL is set,
# checking if we need explicit init.

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@auth_bp.route('/profile/logo', methods=['POST'])
@jwt_required()
def upload_logo():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
        
    if file and allowed_file(file.filename):
        # Configure Cloudinary
        cloudinary.config( 
            cloud_name = current_app.config['CLOUDINARY_CLOUD_NAME'], 
            api_key = current_app.config['CLOUDINARY_API_KEY'], 
            api_secret = current_app.config['CLOUDINARY_API_SECRET'] 
        )

        try:
            # Upload to Cloudinary
            current_user_id = get_jwt_identity()
            upload_result = cloudinary.uploader.upload(
                file, 
                public_id=f"user_{current_user_id}_logo",
                folder="bizflow_logos",
                overwrite=True,
                resource_type="image"
            )
            
            # Get secure URL
            logo_url = upload_result.get('secure_url')
            
            # Update User Profile
            user = User.query.get(current_user_id)
            user.logo_url = logo_url
            db.session.commit()
            
            return jsonify({"message": "Logo uploaded successfully", "logo_url": logo_url}), 200
            
        except Exception as e:
            print(f"Cloudinary Error: {e}")
            return jsonify({"message": "Failed to upload to Cloudinary"}), 500
        
    return jsonify({"message": "File type not allowed"}), 400

from .models import Announcement

@auth_bp.route('/announcements/active', methods=['GET'])
def get_active_announcement():
    active = Announcement.query.filter_by(is_active=True).first()
    if active:
        return jsonify({"status": "success", "data": active.to_dict()}), 200
    return jsonify({"status": "success", "data": None}), 200
