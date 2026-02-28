from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.modules.services.models import Service, Availability, Booking
from datetime import datetime

services_bp = Blueprint('services', __name__)

# --- SERVICES endpoints ---

@services_bp.route('/', methods=['GET'])
@jwt_required()
def get_services():
    user_id = get_jwt_identity()
    services = Service.query.filter_by(user_id=user_id).all()
    return jsonify([s.to_dict() for s in services]), 200

@services_bp.route('/', methods=['POST'])
@jwt_required()
def create_service():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or not data.get('name') or not data.get('price'):
        return jsonify({'error': 'Name and price are required'}), 400
        
    service = Service(
        user_id=user_id,
        name=data.get('name'),
        description=data.get('description', ''),
        service_type=data.get('service_type', 'in_shop'),
        price=float(data.get('price')),
        duration=int(data.get('duration', 30)),
        is_active=data.get('is_active', True)
    )
    db.session.add(service)
    db.session.commit()
    
    return jsonify(service.to_dict()), 201

@services_bp.route('/<int:service_id>', methods=['PUT'])
@jwt_required()
def update_service(service_id):
    user_id = get_jwt_identity()
    service = Service.query.filter_by(id=service_id, user_id=user_id).first()
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
        
    data = request.get_json()
    
    if 'name' in data:
        service.name = data['name']
    if 'description' in data:
        service.description = data['description']
    if 'service_type' in data:
        service.service_type = data['service_type']
    if 'price' in data:
        service.price = float(data['price'])
    if 'duration' in data:
        service.duration = int(data['duration'])
    if 'is_active' in data:
        service.is_active = data['is_active']
        
    db.session.commit()
    return jsonify(service.to_dict()), 200

@services_bp.route('/<int:service_id>', methods=['DELETE'])
@jwt_required()
def delete_service(service_id):
    user_id = get_jwt_identity()
    service = Service.query.filter_by(id=service_id, user_id=user_id).first()
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
        
    db.session.delete(service)
    db.session.commit()
    return jsonify({'message': 'Service deleted'}), 200

# --- AVAILABILITY endpoints ---

@services_bp.route('/schedule', methods=['GET'])
@jwt_required()
def get_schedule():
    user_id = get_jwt_identity()
    availabilities = Availability.query.filter_by(user_id=user_id).order_by(Availability.day_of_week).all()
    
    # If the user has no schedule, return a default initialized list (but do not commit to DB until they save)
    if not availabilities:
        default_schedule = []
        for i in range(7):
            # Mon-Fri (0-4) default active 09:00-17:00, Sat-Sun (5-6) inactive
            default_schedule.append({
                'day_of_week': i,
                'start_time': '09:00',
                'end_time': '17:00',
                'is_active': i < 5
            })
        return jsonify(default_schedule), 200
        
    return jsonify([a.to_dict() for a in availabilities]), 200

@services_bp.route('/schedule', methods=['POST'])
@jwt_required()
def update_schedule():
    user_id = get_jwt_identity()
    schedule_data = request.get_json()
    
    if not isinstance(schedule_data, list):
        return jsonify({'error': 'Expected a list of daily availabilities'}), 400
        
    # Clear existing schedule
    Availability.query.filter_by(user_id=user_id).delete()
    
    new_availabilities = []
    for day in schedule_data:
        try:
            start_time = datetime.strptime(day.get('start_time', '09:00'), '%H:%M').time()
            end_time = datetime.strptime(day.get('end_time', '17:00'), '%H:%M').time()
            
            avail = Availability(
                user_id=user_id,
                day_of_week=int(day['day_of_week']),
                start_time=start_time,
                end_time=end_time,
                is_active=bool(day.get('is_active', False))
            )
            db.session.add(avail)
            new_availabilities.append(avail)
        except Exception as e:
            return jsonify({'error': f"Invalid time format for day {day.get('day_of_week')}: {str(e)}"}), 400
            
    db.session.commit()
    return jsonify([a.to_dict() for a in new_availabilities]), 200

# --- BOOKINGS endpoints ---

@services_bp.route('/bookings', methods=['GET'])
@jwt_required()
def get_bookings():
    user_id = get_jwt_identity()
    bookings = Booking.query.filter_by(user_id=user_id).order_by(Booking.booking_date.desc(), Booking.booking_time.desc()).all()
    return jsonify([b.to_dict() for b in bookings]), 200

@services_bp.route('/bookings/<int:booking_id>/status', methods=['PUT'])
@jwt_required()
def update_booking_status(booking_id):
    user_id = get_jwt_identity()
    booking = Booking.query.filter_by(id=booking_id, user_id=user_id).first()
    
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
        
    data = request.get_json()
    if 'status' in data:
        # e.g., Confirmed, Completed, Cancelled
        booking.status = data['status']
        db.session.commit()
        return jsonify(booking.to_dict()), 200
        
    return jsonify({'error': 'Status is required'}), 400
