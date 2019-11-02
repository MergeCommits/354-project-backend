from functools import wraps, update_wrapper
from flask import g, session, make_response, request, current_app
from flaskr.models.User import User
from flaskr.db import session_scope
import os

def not_login(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if 'user_id' in session:
            return {
                'code': 400,
                'message': 'Forbidden Access'
            }, 400
        return func(*args, **kwargs)
    return decorated_function

def login_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if 'user' not in g:
            return {
                'code': 400,
                'message': 'Unauthorized Access'
            }, 400

        return func(*args, **kwargs)
    return decorated_function

def cross_origin(origin=os.environ.get('FLASK_ORIGIN') or '*', methods=["GET", "PUT", "POST", "DELETE", "OPTIONS"], headers=["Origin", "X-Requested-With", "Content-Type", "Accept"]):
    def _cross_origin_factory(func):
        def _cross_origin(*args, **kwargs):
            if request.method != 'OPTIONS':
                response = make_response(func(*args, **kwargs))
            else:
                response = make_response()

            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = ", ".join(headers)
            response.headers["Access-Control-Allow-Methods"] = ", ".join(methods)
            # Tells the browser to expose the response to frontend when cross-origin cookies are transferred.
            response.headers["Access-Control-Allow-Credentials"] = "true"
            # Explicitly allows cross-site cookies. The 'Secure' directive doesn't actually work since we're
            # not on https.
            response.headers.add('Set-Cookie','SameSite=None; Secure')

            return response
        return update_wrapper(_cross_origin, func)
    return _cross_origin_factory

def is_logged_in():
    if 'user' in g:
        return True
    else:
        return False