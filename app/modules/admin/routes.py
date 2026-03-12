from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta

from app.modules.auth.models import User, Announcement, CreditTransaction, WaitlistEntry
from app.modules.invoices.models import Invoice, Customer
from app.modules.products.models import Product

from . import admin_bp

@admin_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_admin_stats():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_admin:
        return jsonify({"message": "Admin privileges required"}), 403

    # Total Users
    total_users = User.query.count()
    
    # Total Invoices
    total_invoices = Invoice.query.count()
    
    # Total Platform Revenue (Sum of all Paid invoices)
    total_revenue = db.session.query(func.sum(Invoice.total_amount)).filter_by(status='Paid').scalar() or 0.0
    
    # Total Circulating Credits
    total_credits = db.session.query(func.sum(User.kasi_credits)).scalar() or 0
    
    # Total Products Created
    total_products = Product.query.count()
    
    # List of Users (simplistic view for admin dashboard)
    # Could paginate this later, but useful for a quick MVP admin
    users = User.query.order_by(User.created_at.desc()).limit(50).all()
    user_list = [
        {
            "id": u.id,
            "business_name": u.business_name,
            "email": u.email,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "is_admin": u.is_admin,
            "kasi_credits": u.kasi_credits
        } for u in users
    ]

    return jsonify({
        "status": "success",
        "data": {
            "total_users": total_users,
            "total_invoices": total_invoices,
            "total_platform_revenue": float(total_revenue),
            "total_platform_credits": total_credits,
            "total_products": total_products,
            "users": user_list
        }
    }), 200

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def get_admin_users():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_admin:
        return jsonify({"message": "Admin privileges required"}), 403

    users = User.query.order_by(User.created_at.desc()).all()
    user_list = []
    
    for u in users:
        # Calculate their specific stats
        u_invoices = Invoice.query.filter_by(user_id=u.id).all()
        u_paid_revenue = sum(inv.total_amount for inv in u_invoices if inv.status == 'Paid')
        
        user_list.append({
            "id": u.id,
            "business_name": u.business_name,
            "email": u.email,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "is_admin": u.is_admin,
            "total_invoices": len(u_invoices),
            "total_revenue": float(u_paid_revenue),
            "kasi_credits": u.kasi_credits
        })

    return jsonify({
        "status": "success",
        "data": user_list
    }), 200

@admin_bp.route('/invoices', methods=['GET'])
@jwt_required()
def get_admin_invoices():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_admin:
        return jsonify({"message": "Admin privileges required"}), 403

    # Load all invoices globally, joined with User to get business name
    invoices = Invoice.query.order_by(Invoice.id.desc()).all()
    
    invoice_list = []
    for inv in invoices:
        business_owner = User.query.get(inv.user_id)
        
        invoice_list.append({
            "id": inv.id,
            "reference": inv.reference,
            "customer_name": inv.customer_name if hasattr(inv, 'customer_name') else "Unknown",
            "date_issued": inv.date_issued if isinstance(inv.date_issued, str) else (inv.date_issued.strftime('%Y-%m-%d') if inv.date_issued else ""),
            "due_date": inv.due_date if isinstance(inv.due_date, str) else (inv.due_date.strftime('%Y-%m-%d') if inv.due_date else ""),
            "total_amount": float(inv.total_amount),
            "status": inv.status,
            "business_name": business_owner.business_name if business_owner else "Deleted User"
        })
    return jsonify({
        "status": "success",
        "data": invoice_list
    }), 200

@admin_bp.route('/users/<int:target_user_id>', methods=['GET'])
@jwt_required()
def get_admin_user_detail(target_user_id):
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)
    
    if not admin_user or not admin_user.is_admin:
        return jsonify({"message": "Admin privileges required"}), 403

    target_user = User.query.get(target_user_id)
    if not target_user:
        return jsonify({"message": "User not found"}), 404

    # Get their products
    products = Product.query.filter_by(user_id=target_user_id).all()
    product_list = [p.to_dict() for p in products]

    # Get their clients (Customers)
    from app.modules.invoices.models import Customer
    clients = Customer.query.filter_by(user_id=target_user_id).all()
    client_list = [c.to_dict() for c in clients]

    # Get their invoices
    invoices = Invoice.query.filter_by(user_id=target_user_id).order_by(Invoice.created_at.desc()).all()
    invoice_list = [inv.to_dict() for inv in invoices] # This includes line items from the model method

    return jsonify({
        "status": "success",
        "data": {
            "id": target_user.id,
            "business_name": target_user.business_name,
            "email": target_user.email,
            "created_at": target_user.created_at.isoformat() if target_user.created_at else None,
            "kasi_credits": target_user.kasi_credits,
            "products": product_list,
            "clients": client_list,
            "invoices": invoice_list
        }
    }), 200


@admin_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
@jwt_required()
def get_admin_invoice_detail(invoice_id):
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)
    
    if not admin_user or not admin_user.is_admin:
        return jsonify({"message": "Admin privileges required"}), 403

    inv = Invoice.query.get(invoice_id)
    if not inv:
        return jsonify({"message": "Invoice not found"}), 404

    return jsonify({
        "status": "success",
        "data": inv.to_dict()
    }), 200

from flask import request
import random
import string

@admin_bp.route('/list-admins', methods=['GET'])
@jwt_required()
def list_admins():
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)
    
    # Only a Super Admin can list staff
    if not admin_user or not admin_user.is_admin or admin_user.admin_role != 'Super Admin':
        return jsonify({"message": "Super Admin privileges required"}), 403

    staff = User.query.filter(User.is_admin == True).all()
    staff_list = [u.to_dict() for u in staff]

    return jsonify({
        "status": "success",
        "data": staff_list
    }), 200

@admin_bp.route('/create-admin', methods=['POST'])
@jwt_required()
def create_admin():
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)

    # Only a Super Admin can create other admins
    if not admin_user or not admin_user.is_admin or admin_user.admin_role != 'Super Admin':
        return jsonify({"message": "Super Admin privileges required"}), 403

    data = request.get_json()
    email = data.get('email')
    role = data.get('admin_role')
    first_name = data.get('first_name', 'Admin')

    if not email or not role:
        return jsonify({"message": "Email and admin_role are required"}), 400
        
    valid_roles = ['Super Admin', 'Finance Admin', 'Support Admin']
    if role not in valid_roles:
         return jsonify({"message": f"Invalid role. Must be one of {valid_roles}"}), 400

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        # Upgrade existing user
        existing_user.is_admin = True
        existing_user.admin_role = role
        db.session.commit()
        return jsonify({
            "status": "success", 
            "message": f"Existing user upgraded to {role}.",
            "data": existing_user.to_dict()
        }), 200
    else:
        # Create brand new user record for the staff member
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        new_admin = User(
            email=email,
            business_name=f"Kasi {role} ({first_name})",
            is_admin=True,
            admin_role=role
        )
        new_admin.set_password(temp_password)
        
        db.session.add(new_admin)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"New {role} created.",
            "data": new_admin.to_dict(),
            "temp_password": temp_password # In production, this should ideally be an email invite link
        }), 201

@admin_bp.route('/users/<int:target_user_id>/status', methods=['POST'])
@jwt_required()
def update_user_status(target_user_id):
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)
    
    # Only Super Admin and Support Admin can moderate users
    if not admin_user or not admin_user.is_admin or admin_user.admin_role not in ['Super Admin', 'Support Admin']:
        return jsonify({"message": "Privileges required to moderate users"}), 403

    target_user = User.query.get(target_user_id)
    if not target_user:
        return jsonify({"message": "User not found"}), 404
        
    # Prevent Admins from suspending themselves or other super admins
    if target_user.id == admin_user.id:
        return jsonify({"message": "You cannot modify your own status"}), 400
    if target_user.is_admin and target_user.admin_role == 'Super Admin':
        return jsonify({"message": "Cannot modify status of a Super Admin"}), 403

    data = request.get_json()
    new_status = data.get('account_status')
    
    valid_statuses = ['active', 'suspended', 'banned']
    if new_status not in valid_statuses:
        return jsonify({"message": f"Invalid status. Must be one of {valid_statuses}"}), 400

    target_user.account_status = new_status
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"User status updated to {new_status}",
        "data": target_user.to_dict()
    }), 200

@admin_bp.route('/users/<int:target_user_id>/impersonate', methods=['POST'])
@jwt_required()
def impersonate(target_user_id):
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)
    
    if not admin_user or not admin_user.is_admin or admin_user.admin_role not in ['Super Admin', 'Support Admin']:
        return jsonify({"message": "Privileges required to impersonate users"}), 403

    target_user = User.query.get(target_user_id)
    if not target_user:
        return jsonify({"message": "User not found"}), 404

    from flask_jwt_extended import create_access_token
    access_token = create_access_token(identity=str(target_user.id))

    return jsonify({
        "status": "success",
        "message": f"Impersonating {target_user.business_name}",
        "access_token": access_token,
        "user": target_user.to_dict()
    }), 200

@admin_bp.route('/announcements', methods=['GET', 'POST'])
@jwt_required()
def manage_announcements():
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)
    
    if not admin_user or not admin_user.is_admin or admin_user.admin_role not in ['Super Admin', 'Support Admin']:
        return jsonify({"message": "Privileges required"}), 403

    if request.method == 'POST':
        data = request.get_json()
        
        # Deactivate previous active announcements
        if data.get('is_active', True):
            Announcement.query.filter_by(is_active=True).update({'is_active': False})
            
        new_announcement = Announcement(
            title=data.get('title'),
            message=data.get('message'),
            type=data.get('type', 'info'),
            is_active=data.get('is_active', True)
        )
        db.session.add(new_announcement)
        db.session.commit()
        return jsonify({"status": "success", "data": new_announcement.to_dict()}), 201

    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return jsonify({
        "status": "success",
        "data": [a.to_dict() for a in announcements]
    }), 200

@admin_bp.route('/announcements/<int:announcement_id>/toggle', methods=['POST'])
@jwt_required()
def toggle_announcement(announcement_id):
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)
    
    if not admin_user or not admin_user.is_admin or admin_user.admin_role not in ['Super Admin', 'Support Admin']:
        return jsonify({"message": "Privileges required"}), 403

    announcement = Announcement.query.get(announcement_id)
    if not announcement:
        return jsonify({"message": "Announcement not found"}), 404

    announcement.is_active = not announcement.is_active
    
    if announcement.is_active:
        # Deactivate others
        Announcement.query.filter(Announcement.id != announcement_id, Announcement.is_active == True).update({'is_active': False})

    db.session.commit()
    return jsonify({"status": "success", "data": announcement.to_dict()}), 200

@admin_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_admin_transactions():
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)
    
    if not admin_user or not admin_user.is_admin or admin_user.admin_role not in ['Super Admin', 'Finance Admin']:
        return jsonify({"message": "Finance Admin privileges required"}), 403

    # Load all transactions, joined with User to get business name
    # We order by created_at descending so newest are first
    transactions = CreditTransaction.query.order_by(CreditTransaction.created_at.desc()).all()
    
    tx_list = []
    for tx in transactions:
        business_owner = User.query.get(tx.user_id)
        
        tx_list.append({
            "id": tx.id,
            "reference_id": tx.reference_id,
            "amount": float(tx.amount),
            "description": tx.description,
            "transaction_type": tx.transaction_type,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
            "business_name": business_owner.business_name if business_owner else "Deleted User",
            "email": business_owner.email if business_owner else "Unknown"
        })
        
    return jsonify({
        "status": "success",
        "data": tx_list
    }), 200

@admin_bp.route('/waitlist', methods=['GET'])
@jwt_required()
def get_admin_waitlist():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_admin:
        return jsonify({"message": "Admin privileges required"}), 403

    entries = WaitlistEntry.query.order_by(WaitlistEntry.created_at.desc()).all()
    return jsonify([e.to_dict() for e in entries]), 200

@admin_bp.route('/audit-logs', methods=['GET'])
@jwt_required()
def get_admin_audit_logs():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_admin:
        return jsonify({"message": "Admin privileges required"}), 403
        
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int) # Admins see more at once
    action_filter = request.args.get('action')
    
    from app.modules.auth.models import AuditLog
    
    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    
    if action_filter:
        query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
        
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    logs_data = []
    for log in pagination.items:
        # Fetch associated user for admin visibility
        log_user = log.user
        user_info = None
        if log_user:
            user_info = {
                 "id": log_user.id,
                 "email": log_user.email,
                 "business_name": log_user.business_name
            }
            
        logs_data.append({
            'id': log.id,
            'user': user_info,
            'action': log.action,
            'resource_details': log.resource_details,
            'ip_address': log.ip_address,
            'created_at': log.created_at.isoformat()
        })
        
    return jsonify({
        'logs': logs_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200
