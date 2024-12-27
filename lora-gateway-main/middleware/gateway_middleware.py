from functools import wraps
from flask import jsonify
from helper.gateway_storage import GatewayStorage

def require_gateway_enrollment(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        gateway_storage = GatewayStorage()
        if not gateway_storage.is_enrolled():
            return jsonify({
                'message': 'Gateway not enrolled. Please enroll gateway first.',
                'status': 'unenrolled'
            }), 403
        return f(*args, **kwargs)
    return decorated_function
