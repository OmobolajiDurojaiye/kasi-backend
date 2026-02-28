import random
from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from sqlalchemy import func

from app.modules.invoices.models import Invoice
from app.modules.products.models import Product

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/', methods=['GET'])
@jwt_required()
def get_analytics():
    user_id = get_jwt_identity()

    # Total Agent Revenue: sum of all 'Paid' invoices for this user
    paid_invoices = Invoice.query.filter_by(user_id=user_id, status='Paid').all()
    
    total_revenue = sum(inv.total_amount for inv in paid_invoices)
    
    # Total Products
    total_products = Product.query.filter_by(user_id=user_id).count()

    # Average Order Value
    avg_order_value = total_revenue / len(paid_invoices) if paid_invoices else 0.0

    # Chart Data: Actually sum the revenue per day for the last 30 days
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=29)
    
    # Initialize dictionary with past 30 days
    daily_revenue = {}
    for i in range(30):
        day = start_date + timedelta(days=i)
        daily_revenue[day.strftime('%d %b %Y')] = 0.0
        
    # Aggregate paid invoices by their issue date
    # Assuming the date_issued structure is mostly a datetime object or standard date string format
    for inv in paid_invoices:
        if inv.date_issued:
            # Check if it's within the last 30 days
            if isinstance(inv.date_issued, str):
                try:
                    # Handle typical date string variants if needed (optional parsing buffer)
                    inv_date = datetime.strptime(inv.date_issued, '%Y-%m-%d').date()
                except ValueError:
                    continue # Ignore format issues or add proper parsing
            else:
                inv_date = inv.date_issued.date() if hasattr(inv.date_issued, 'date') else inv.date_issued

            if start_date <= inv_date <= today:
                date_key = inv_date.strftime('%d %b %Y')
                daily_revenue[date_key] += float(inv.total_amount)

    chart_data = [{"name": date, "value": round(amount, 2)} for date, amount in daily_revenue.items()]

    return jsonify({
        "status": "success",
        "data": {
            "total_agent_revenue": total_revenue,
            "click_through_rate": 35, # Static for now
            "total_clicks": 2351, # Static for now
            "ai_resolution_rate": 91.8, # Static for now
            "ai_drop_off_rate": 8.2, # Static for now
            "total_recommended_products": total_products,
            "average_order_value": avg_order_value,
            "average_conversation_length": "3m 21s", # Static for now
            "chart_data": chart_data
        }
    }), 200
