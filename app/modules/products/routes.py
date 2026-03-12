import cloudinary
import cloudinary.uploader
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from .models import Product
from app.services.security_service import AuditService

products_bp = Blueprint('products', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── List all products ──────────────────────────────────
@products_bp.route('/', methods=['GET'])
@jwt_required()
def list_products():
    user_id = get_jwt_identity()
    products = Product.query.filter_by(user_id=user_id).order_by(Product.created_at.desc()).all()
    return jsonify([p.to_dict() for p in products]), 200


# ── Create product ─────────────────────────────────────
@products_bp.route('/', methods=['POST'])
@jwt_required()
def create_product():
    user_id = get_jwt_identity()
    data = request.get_json()

    if not data.get('name') or data.get('price') is None:
        return jsonify({"error": "Name and price are required"}), 400

    product = Product(
        user_id=user_id,
        name=data['name'],
        description=data.get('description', ''),
        price=float(data['price']),
        min_price=float(data['min_price']) if data.get('min_price') else None,
        in_stock=data.get('in_stock', True),
    )
    db.session.add(product)
    db.session.commit()
    
    AuditService.log_action(user_id, "PRODUCT_CREATED", {"product_id": product.id, "name": product.name, "price": product.price})
    
    return jsonify(product.to_dict()), 201


# ── Update product ─────────────────────────────────────
@products_bp.route('/<int:product_id>', methods=['PATCH'])
@jwt_required()
def update_product(product_id):
    user_id = get_jwt_identity()
    product = Product.query.filter_by(id=product_id, user_id=user_id).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    data = request.get_json()
    if 'name' in data:
        product.name = data['name']
    if 'description' in data:
        product.description = data['description']
    if 'price' in data:
        product.price = float(data['price'])
    if 'min_price' in data:
        product.min_price = float(data['min_price']) if data['min_price'] else None
    if 'in_stock' in data:
        product.in_stock = bool(data['in_stock'])

    db.session.commit()
    return jsonify(product.to_dict()), 200


# ── Delete product ─────────────────────────────────────
@products_bp.route('/<int:product_id>', methods=['DELETE'])
@jwt_required()
def delete_product(product_id):
    user_id = get_jwt_identity()
    product = Product.query.filter_by(id=product_id, user_id=user_id).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    db.session.delete(product)
    db.session.commit()
    
    AuditService.log_action(user_id, "PRODUCT_DELETED", {"product_id": product_id, "name": product.name})
    
    return jsonify({"message": "Product deleted"}), 200


# ── Upload product image ──────────────────────────────
@products_bp.route('/<int:product_id>/image', methods=['POST'])
@jwt_required()
def upload_image(product_id):
    user_id = get_jwt_identity()
    product = Product.query.filter_by(id=product_id, user_id=user_id).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    cloudinary.config(
        cloud_name=current_app.config['CLOUDINARY_CLOUD_NAME'],
        api_key=current_app.config['CLOUDINARY_API_KEY'],
        api_secret=current_app.config['CLOUDINARY_API_SECRET'],
    )

    try:
        result = cloudinary.uploader.upload(
            file,
            public_id=f"product_{product_id}",
            folder="bizflow_products",
            overwrite=True,
            resource_type="image",
        )
        product.image_url = result.get('secure_url')
        db.session.commit()
        return jsonify({"message": "Image uploaded", "image_url": product.image_url}), 200
    except Exception as e:
        print(f"Cloudinary Error: {e}")
        return jsonify({"error": "Failed to upload image"}), 500
