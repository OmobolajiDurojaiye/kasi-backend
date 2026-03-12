from flask import Blueprint, jsonify, request
from app.extensions import db, limiter
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.modules.auth.models import User, CreditTransaction
from app.services.paystack_service import PaystackService
from app.services.security_service import AuditService, require_idempotency
from datetime import datetime
import uuid

billing_bp = Blueprint('billing', __name__)

# Available credit packages
CREDIT_PACKAGES = {
    'pkg_100': {'credits': 100, 'price_ngn': 2000, 'name': '100 Kasi Credits'},
    'pkg_500': {'credits': 500, 'price_ngn': 9000, 'name': '500 Kasi Credits (10% Off)'},
    'pkg_1000': {'credits': 1000, 'price_ngn': 16000, 'name': '1000 Kasi Credits (20% Off)'}
}

@billing_bp.route('/wallet', methods=['GET'])
@jwt_required()
def get_wallet():
    """Retrieve the user's current Kasi Credit balance and transaction history."""
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    # Get last 20 transactions
    transactions = CreditTransaction.query.filter_by(user_id=current_user_id)\
        .order_by(CreditTransaction.created_at.desc())\
        .limit(20)\
        .all()
        
    return jsonify({
        'kasi_credits': user.kasi_credits,
        'transactions': [t.to_dict() for t in transactions]
    }), 200

@billing_bp.route('/packages', methods=['GET'])
@jwt_required()
def get_packages():
    """Return available top-up packages."""
    return jsonify(CREDIT_PACKAGES), 200

@billing_bp.route('/initialize-topup', methods=['POST'])
@limiter.limit("10 per minute") # Also rate limit this endpoint
@jwt_required()
@require_idempotency
def initialize_topup():
    """Trigger Paystack to generate a checkout session for purchasing credits."""
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    data = request.get_json()
    package_id = data.get('package_id')
    
    if not package_id or package_id not in CREDIT_PACKAGES:
        return jsonify({'error': 'Invalid package selected.'}), 400
        
    package = CREDIT_PACKAGES[package_id]
    amount = package['price_ngn']
    
    # Generate unique reference
    reference = f"TUP-{user.id}-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6]}"
    
    # Use real email or fallback
    email = user.email or f"user{user.id}@kasi.com"
    
    qt_res = PaystackService.initialize_transaction(
        email=email,
        amount=amount,
        reference=reference,
        callback_url=data.get('callback_url')
    )
    
    if qt_res and qt_res.get('status'):
        AuditService.log_action(user.id, "TOPUP_INITIALIZED", {"package": package_id, "amount": amount, "reference": reference})
        return jsonify({
            'authorization_url': qt_res['data']['authorization_url'],
            'reference': reference,
            'package': package
        }), 200
    else:
        return jsonify({'error': 'Failed to initialize Paystack transaction.'}), 500

@billing_bp.route('/verify-topup', methods=['POST'])
@jwt_required()
@require_idempotency
def verify_topup():
    """Verify Paystack transaction and award Kasi Credits."""
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    data = request.get_json()
    reference = data.get('reference')
    package_id = data.get('package_id')
    
    if not reference or not package_id or package_id not in CREDIT_PACKAGES:
        return jsonify({'error': 'Invalid request parameters.'}), 400
        
    # Prevent duplicate processing by checking if reference already exists
    existing = CreditTransaction.query.filter_by(reference_id=reference).first()
    if existing:
        return jsonify({'message': 'Transaction already processed', 'kasi_credits': user.kasi_credits}), 200
        
    verify_res = PaystackService.verify_transaction(reference)
    
    if verify_res and verify_res.get('status') and verify_res['data']['status'] == 'success':
        package = CREDIT_PACKAGES[package_id]
        
        # Award credits
        user.kasi_credits += package['credits']
        
        # Log transaction
        log = CreditTransaction(
            user_id=user.id,
            amount=package['credits'],
            transaction_type='purchase',
            reference_id=reference,
            description=f"Purchased {package['name']}"
        )
        
        db.session.add(log)
        db.session.commit()
        
        AuditService.log_action(user.id, "TOPUP_VERIFIED_SUCCESS", {"package": package_id, "credits_added": package['credits'], "reference": reference})
        
        return jsonify({
            'message': 'Top-up successful!',
            'kasi_credits': user.kasi_credits
        }), 200
    else:
        return jsonify({'error': 'Transaction verification failed or not completed.'}), 400
