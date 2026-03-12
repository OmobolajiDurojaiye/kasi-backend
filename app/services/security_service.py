import json
from flask import request
from app.extensions import db
from app.modules.auth.models import AuditLog, IdempotencyKey
from functools import wraps
from flask import jsonify

class AuditService:
    @staticmethod
    def log_action(user_id, action, resource_details=None):
        """
        Logs a critical action to the AuditLog table for compliance/security.
        """
        try:
            ip_address = request.remote_addr
            
            # Serialize dict to JSON string if needed
            details_str = None
            if isinstance(resource_details, dict) or isinstance(resource_details, list):
                details_str = json.dumps(resource_details)
            elif resource_details:
                details_str = str(resource_details)

            log = AuditLog(
                user_id=user_id,
                action=action,
                resource_details=details_str,
                ip_address=ip_address
            )
            db.session.add(log)
            db.session.commit()
            return True
        except Exception as e:
            print(f"[AuditService] Failed to log action '{action}': {e}")
            db.session.rollback()
            return False

def require_idempotency(f):
    """
    Decorator to ensure that retried POST requests (e.g. double clicks) 
    do not result in duplicate state changes or charges. 
    It checks for the 'Idempotency-Key' header.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        idempotency_key = request.headers.get('Idempotency-Key')
        
        # If no key provided, just run normally (or you could reject with 400, but let's be safe for MVP)
        if not idempotency_key:
            return f(*args, **kwargs)

        # Check if we already processed this key
        existing_key = IdempotencyKey.query.filter_by(key=idempotency_key).first()
        if existing_key:
            # We already processed this request! Return the cached exact response to prevent double-charging.
            try:
                cached_body = json.loads(existing_key.response_body)
                return jsonify(cached_body), existing_key.response_code
            except Exception as e:
                print(f"[Idempotency] Failed to load cached response for key {idempotency_key}: {e}")
                pass # Fallback to normal execution if cache read fails
        
        # We have NOT seen this key. Execute the route logic normally.
        response = f(*args, **kwargs)
        
        # Extract the response data from Flask's Return tuple (typically jsonify(dict), int)
        # response can be a Response object or a tuple (Response, status_code)
        resp_obj = response
        status_code = 200
        
        if isinstance(response, tuple):
            resp_obj = response[0]
            if len(response) > 1:
                status_code = response[1]
        elif hasattr(response, 'status_code'):
            status_code = response.status_code
            
        # Only cache successful or bad request responses (don't cache 500 server errors, user should retry those)
        if 200 <= status_code < 500 and hasattr(resp_obj, 'get_data'):
            try:
                body_str = resp_obj.get_data(as_text=True)
                new_key = IdempotencyKey(
                    key=idempotency_key,
                    response_code=status_code,
                    response_body=body_str
                )
                db.session.add(new_key)
                db.session.commit()
            except Exception as e:
                print(f"[Idempotency] Failed to save response for key {idempotency_key}: {e}")
                db.session.rollback()
                
        return response
        
    return decorated_function
