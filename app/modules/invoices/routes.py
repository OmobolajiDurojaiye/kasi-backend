from flask import Blueprint, request, jsonify
from app.extensions import db
from .models import Invoice, Customer, InvoiceItem
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from app.services.pdf_service import PDFService

invoices_bp = Blueprint('invoices', __name__)

@invoices_bp.route('/', methods=['POST'])
@jwt_required()
def create_invoice():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # 1. Handle Customer (Create new or use existing)
    customer_id = data.get('customer_id')
    if not customer_id:
        # Create new customer
        new_customer = Customer(
            user_id=current_user_id,
            name=data['customer_name'],
            email=data.get('customer_email'),
            phone=data.get('customer_phone'),
            address=data.get('customer_address')
        )
        db.session.add(new_customer)
        db.session.flush() # Get ID without committing
        customer_id = new_customer.id

    # 2. Create Invoice
    new_invoice = Invoice(
        user_id=current_user_id,
        customer_id=customer_id,
        reference=data['reference'],
        date_issued=datetime.strptime(data['date_issued'], '%Y-%m-%d').date(),
        due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date(),
        status=data.get('status', 'Draft'),
        subtotal=data['subtotal'],
        tax_amount=data['tax_amount'],
        total_amount=data['total_amount']
    )
    db.session.add(new_invoice)
    db.session.flush()

    # 3. Create Invoice Items
    for item in data['items']:
        invoice_item = InvoiceItem(
            invoice_id=new_invoice.id,
            description=item['description'],
            quantity=item['quantity'],
            unit_price=item['unit_price'],
            total_price=item['total_price']
        )
        db.session.add(invoice_item)

    db.session.commit() # Commit to get ID and ensure data is saved before generating PDF

    # 4. Generate PDF
    try:
        pdf_url = PDFService.generate_invoice_pdf(new_invoice.to_dict())
        new_invoice.pdf_url = pdf_url
    except Exception as e:
        print(f"Error generating PDF: {e}")

    db.session.commit()
    return jsonify(new_invoice.to_dict()), 201

@invoices_bp.route('/', methods=['GET'])
@jwt_required()
def get_invoices():
    current_user_id = get_jwt_identity()
    invoices = Invoice.query.filter_by(user_id=current_user_id).order_by(Invoice.created_at.desc()).all()
    return jsonify([inv.to_dict() for inv in invoices]), 200

@invoices_bp.route('/<int:id>', methods=['GET'])
@jwt_required()
def get_invoice(id):
    current_user_id = get_jwt_identity()
    invoice = Invoice.query.filter_by(id=id, user_id=current_user_id).first_or_404()
    return jsonify(invoice.to_dict()), 200

@invoices_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_invoice(id):
    current_user_id = get_jwt_identity()
    invoice = Invoice.query.filter_by(id=id, user_id=current_user_id).first_or_404()
    
    db.session.delete(invoice)
    db.session.commit()
    
    return jsonify({'message': 'Invoice deleted successfully'}), 200

@invoices_bp.route('/<int:id>', methods=['PATCH'])
@jwt_required()
def update_invoice(id):
    current_user_id = get_jwt_identity()
    invoice = Invoice.query.filter_by(id=id, user_id=current_user_id).first_or_404()
    data = request.get_json()
    
    if 'status' in data:
        invoice.status = data['status']
        
    db.session.commit()
    return jsonify(invoice.to_dict()), 200

@invoices_bp.route('/<int:id>/pdf', methods=['GET'])
@jwt_required()
def get_invoice_pdf(id):
    current_user_id = get_jwt_identity()
    invoice = Invoice.query.filter_by(id=id, user_id=current_user_id).first_or_404()
    
    # Regenerate PDF to ensure latest branding/data
    try:
        pdf_url = PDFService.generate_invoice_pdf(invoice.to_dict())
        invoice.pdf_url = pdf_url
        db.session.commit()
        
        # Return full URL if needed, or relative
        return jsonify({'pdf_url': pdf_url}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'message': f"Error generating PDF: {str(e)}"}), 500

@invoices_bp.route('/customers', methods=['GET'])
@jwt_required()
def get_customers():
    current_user_id = get_jwt_identity()
    customers = Customer.query.filter_by(user_id=current_user_id).order_by(Customer.name).all()
    
    # Enrich with some stats? (e.g. total spent) - for MVP just list
    customer_list = []
    for c in customers:
        c_dict = c.to_dict()
        # count invoices?
        c_dict['invoice_count'] = len(c.invoices)
        customer_list.append(c_dict)
        
    return jsonify(customer_list), 200
