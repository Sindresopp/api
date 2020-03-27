from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt_claims
from flask import jsonify

#Wrapper for checking if user are admin
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt_claims()
        if claims['roles'] != 'admin':
            return jsonify(msg='Admins only'), 403
        else:
            return fn(*args, **kwargs)
    return wrapper