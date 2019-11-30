import functools
import re
import os
from jsonschema import validate, draft7_format_checker
import jsonschema.exceptions
import json

from flask import (
    Blueprint, g, request, session, current_app, session
)

from passlib.hash import argon2
from sqlalchemy.exc import DBAPIError
from sqlalchemy import or_
from flaskr.db import session_scope
from flaskr.email import send
from flaskr.models.User import User
from flaskr.models.Cart import Cart
from flaskr.models.Review import Review
from flaskr.models.Order import Order, OrderLine, OrderStatus
from flaskr.routes.utils import login_required, not_login, cross_origin

bp = Blueprint('users', __name__, url_prefix='/users')

@bp.route('', methods=[ 'GET', 'HEAD', 'OPTIONS' ])
@cross_origin(methods=[ 'GET', 'POST', 'HEAD' ])
def listUsers():
    # Validate that only the valid User properties from the JSON schema update_self.schema.json
    schemas_direcotry = os.path.join(current_app.root_path, current_app.config['SCHEMA_FOLDER'])
    schema_filepath = os.path.join(schemas_direcotry, 'users_filter.schema.json')
    try:
        with open(schema_filepath) as schema_file:
            schema = json.loads(schema_file.read())
            validate(instance=request.args, schema=schema, format_checker=draft7_format_checker)
    except jsonschema.exceptions.ValidationError as validation_error:
        return {
            'code': 400,
            'message': validation_error.message
        }, 400

    with session_scope() as db_session:
        query = db_session.query(User)


        if 'username' in request.args:
            query = query.filter(User.username == request.args.get('username'))

        if 'email' in request.args:
            query = query.filter(User.email == request.args.get('email'))

        # If request HEAD send only status of result
        if request.method == 'HEAD':
            if query.count() > 0:
                return '', 200
            else:
                return '', 404
        else:
            users = []
            for user in query.all():
                users.append(user.to_json())

            return {
                "users": users
            }, 200



@bp.route('', methods=['POST', 'OPTIONS'])
@cross_origin(methods=['GET', 'POST', 'HEAD'])
def registerUser():
    """Endpoint use to register a user to the system. Sends a welcoming

    Returns:
        (str, int) -- Returns a tuple of the JSON object of the newly register user and a http status code.
    """

    # Validate that only the valid User properties from the JSON schema update_self.schema.json
    schemas_direcotry = os.path.join(current_app.root_path, current_app.config['SCHEMA_FOLDER'])
    schema_filepath = os.path.join(schemas_direcotry, 'registration.schema.json')
    try:
        with open(schema_filepath) as schema_file:
            schema = json.loads(schema_file.read())
            validate(instance=request.json, schema=schema, format_checker=draft7_format_checker)
    except jsonschema.exceptions.ValidationError as validation_error:
        return {
            'code': 400,
            'message': validation_error.message
        }, 400

    try:
        with session_scope() as db_session:
            new_user = User(first_name=request.json['firstName'], last_name=request.json['lastName'], username=request.json['username'], email=request.json['email'], password=argon2.hash(request.json['password']))
            new_user.reset_password = False
            db_session.add(new_user)

            # Commit new user to database making sure of the integrity of the relations.
            db_session.commit()

            # Automatically login the user upon succesful registration
            session['user_id'] = new_user.id

            # TODO Send confirmation email, for now only sending welcoming email.
            send(current_app.config['SMTP_USERNAME'], new_user.email, "Welcome to 354TheStars!", "<html><body><p>Welcome to 354TheStars!</p></body></html>" ,"Welcome to 354TheStars!")
            new_user.cart = Cart(user_id=new_user.id)
            return new_user.to_json(), 200
    except DBAPIError as db_error:

        # In case that the unvalid user was login remove it from session
        if 'user_id' in session:
            session.pop('user_id')

        # Returns an error in case of a integrity constraint not being followed.
        return {
            'code': 400,
            'message': re.search('DETAIL: (.*)', db_error.args[0]).group(1)
        }, 400

@bp.route('/self', methods=['GET', 'OPTIONS'])
@cross_origin(methods=['GET', 'PATCH'])
@login_required
def showSelf():
    """Endpoint that returns the information of the authenticated user.

    Returns:
        str -- Returns a JSON object of the authenticated user.
    """
    with session_scope() as db_session:
        user = db_session.merge(g.user)

        return user.to_json(), 200

@bp.route('/self', methods=['PATCH', 'OPTIONS'])
@cross_origin(methods=['GET', 'PATCH'])
@login_required
def updateSelf():
    """"Endpoints to handle updating an authenticate user.
    Returns:
        str -- Returns a refreshed instance of user as a JSON or an JSON containing any error encountered.
    """

    # Validate that only the valid User properties from the JSON schema update_self.schema.json
    schemas_direcotry = os.path.join(current_app.root_path, current_app.config['SCHEMA_FOLDER'])
    schema_filepath = os.path.join(schemas_direcotry, 'update_self.schema.json')
    try:
        with open(schema_filepath) as schema_file:
            schema = json.loads(schema_file.read())
            validate(instance=request.json, schema=schema, format_checker=draft7_format_checker)
    except jsonschema.exceptions.ValidationError as validation_error:
        return {
            'code': 400,
            'message': validation_error.message
        }, 400

    try:
        with session_scope() as db_session:
            user = db_session.merge(g.user)
            current_password = request.json.get("current_password")

            # Current User Password is required before applying any changes
            if argon2.verify(current_password, user.password) is False:
                return{
                    'code': 400,
                    'message': "Current password is incorrect"
                }, 400

            # Update the values to the current User
            for k, v in request.json.items():
                # if k == password hash password
                if k == "password":
                    user.__dict__[k] = argon2.hash(v)
                    user.reset_password = False
                else:
                    user.__dict__[k] = v

            db_session.add(user)
            g.user = user
            db_session.expunge(g.user)
            db_session.merge(g.user)

    except DBAPIError as db_error:
        return {
            'code': 400,
            'message': re.search('DETAIL: (.*)', db_error.args[0]).group(1)
        }, 400

    return g.user.to_json(), 200

@bp.route("review", methods =["POST",'OPTION'])
@cross_origin(methods=['POST'])
@login_required
def review():

    # Load json data from json schema to variable user_info.json 'SCHEMA_FOLDER'
    schemas_direcotry = os.path.join(current_app.root_path, current_app.config['SCHEMA_FOLDER'])
    schema_filepath = os.path.join(schemas_direcotry, 'review.schema.json')
    try:
        with open(schema_filepath) as schema_file:
            schema = json.loads(schema_file.read())
            validate(instance=request.json, schema=schema, format_checker=draft7_format_checker)
    except jsonschema.exceptions.ValidationError as validation_error:
        return {
            'code': 400,
            'message': validation_error.message
        }

    try:
        # Check if cart id exists with cart items
        with session_scope() as db_session:

            product_id = request.json.get("product_id")
            comment = request.json.get("comment")
            score = request.json.get("score")

            # check if user has bought this product id
            queryOrder = db_session.query(Order).filter(Order.user_id == g.user.id)

            count = 0
            for item in queryOrder:
                queryOrderLine = db_session.query(OrderLine).filter(OrderLine.order_id == item.id)
                for lineitem in queryOrderLine:
                    if lineitem.product_id == product_id:
                        count = count + 1


            if count > 0:
                if score <= 5 and score >= 0:
                    myreview = Review(user_id=g.user.id,
                            product_id=product_id,
                            comment = comment,
                            score = score
                            )
                    db_session.add(myreview)
                    #db_session.flush()

                    return {
                        "code": 200,
                        "message": myreview.to_json()
                    }, 200
                else:
                    return {
                        "code": 400,
                        "message": "Score has to be in range 0 to 5"
                    }, 400
            else:
                return {
                    "code": 400,
                    "message": "This user can't post review because he hasn't bought any of these products"
                }, 400

    except DBAPIError as db_error:
        # Returns an error in case of a integrity constraint not being followed.
        return {
            'code': 400,
            'message': 'error: ' + db_error.args[0]
        }, 400

@bp.route("replyreview/<string:username>", methods =["POST",'OPTION'])
@cross_origin(methods=['POST'])
@login_required
def replyreview(username):

    # Load json data from json schema to variable user_info.json 'SCHEMA_FOLDER'
    schemas_direcotry = os.path.join(current_app.root_path, current_app.config['SCHEMA_FOLDER'])
    schema_filepath = os.path.join(schemas_direcotry, 'replyreview.schema.json')
    try:
        with open(schema_filepath) as schema_file:
            schema = json.loads(schema_file.read())
            validate(instance=request.json, schema=schema, format_checker=draft7_format_checker)
    except jsonschema.exceptions.ValidationError as validation_error:
        return {
            'code': 400,
            'message': validation_error.message
        }
    try:
        with session_scope() as db_session:
                rev_id = db_session.query(User).filter(User.username == username).one().id
                myreview = db_session.query(Review).filter(Review.user_id == rev_id, Review.product_id == request.json['product_id']).one()


                if myreview.user_id != session['user_id']:
                    return {
                        'code': 400,
                        'message': 'this user cant reply to this review'
                    }, 400
                else:
                    if myreview.reply is not None or myreview.reply == "":
                        return {
                            'code': 400,
                            'message': 'You have already replied to this review'
                        }, 400
                    else:
                        myreview.reply = request.json.get("reply")
                        return {
                            'code': 200,
                            'message': myreview.to_json()
                        }, 200

    except DBAPIError as db_error:
        # Returns an error in case of a integrity constraint not being followed.
        return {
            'code': 400,
            'message': 'error: ' + db_error.args[0]
        }, 400
    
@bp.route("/viewreview/<string:username>", methods =["GET", 'OPTION'])
@cross_origin(methods=['GET'])
@login_required
def viewreview(username):

    try:
        # Check if cart id exists with cart items
        with session_scope() as db_session:
            rev_user_id = db_session.query(User).filter(User.username == username).one().id
            myreview = db_session.query(Review)

            array=[]
            for item in myreview:
                if item.user_id == rev_user_id:
                    array.append(item.to_json())

            return {
                "code": 200,
                "message": array
            }, 200

    except DBAPIError as db_error:
        # Returns an error in case of a integrity constraint not being followed.
        return {
            'code': 400,
            'message': 'error: ' + db_error.args[0]
        }, 400
