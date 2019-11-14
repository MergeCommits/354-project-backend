import functools
import re
import os
from jsonschema import validate, draft7_format_checker
import jsonschema.exceptions
import json

from flask import (
    Blueprint, g, request, session, current_app, session
)

from sqlalchemy.exc import DBAPIError
from sqlalchemy import or_
from flaskr.db import session_scope
from flaskr.email import send
from flaskr.models.User import User
from flaskr.routes.utils import login_required, not_login, cross_origin

bp = Blueprint('addresses', __name__, url_prefix='/addresses')
@bp.route('', methods=['PUT', 'OPTIONS'])
@login_required
@cross_origin(methods=['PUT'])
def addAddress():
    """Endpoint use to add a address to the user. Sends a welcoming

     Returns:
         (str, int) -- Returns a tuple of the JSON object of the newly added addresses and a http status code.
     """
    # Validate that only the valid User properties from the JSON schema update_self.schema.json
    schemas_direcotry = os.path.join(current_app.root_path, current_app.config['SCHEMA_FOLDER'])
    schema_filepath = os.path.join(schemas_direcotry, 'add_addresses.schema.json')
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
            addresses = request.json
            #Check for conflict
            new_address = user.addresses + addresses
            #validate new object according to schema
            # MAX 3 Addresses
            # NO duplicates
            try:
                validate(instance=new_address, schema=schema, format_checker=draft7_format_checker)
            except jsonschema.exceptions.ValidationError as validation_error:
                return {
                           'code': 400,
                           'message': validation_error.message
                       }, 400

            user.addresses = new_address
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

@bp.route('/update', methods=['PATCH', 'OPTIONS'])
@login_required
@cross_origin(methods=['PATCH'])
def updateAddresses():
    """Endpoint use to update one or more address

      Returns:
          (str, int) -- Returns a tuple of the JSON object of the updated addresses and a http status code.
      """
    # Validate that only the valid User properties from the JSON schema update_self.schema.json
    schemas_direcotry = os.path.join(current_app.root_path, current_app.config['SCHEMA_FOLDER'])
    schema_filepath = os.path.join(schemas_direcotry, 'update_addresses.schema.json')
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
            addresses = request.json
            user_address = user.addresses

            for x in range(len(addresses)):
                for k in addresses[x][1]:
                    index = addresses[x][0]
                    new_value = addresses[x][1][k]
                    user_address[index][k] = new_value

            #Check for conflict
            #validate new object according to schema
            # MAX 3 Addresses
            # NO duplicates
            schema_filepath = os.path.join(schemas_direcotry, 'add_addresses.schema.json')
            try:
                with open(schema_filepath) as schema_file:
                    schema = json.loads(schema_file.read())
                    validate(instance=user_address, schema=schema, format_checker=draft7_format_checker)
            except jsonschema.exceptions.ValidationError as validation_error:
                return {
                           'code': 400,
                           'message': validation_error.message
                       }, 400

            user.addresses = user_address
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

@bp.route('', methods=['DELETE', 'OPTIONS'])
@login_required
@cross_origin(methods=['DELETE'])
def delAddress():
        """Endpoint use to add a address to the user. Sends a welcoming

     Returns:
         (str, int) -- Returns a tuple of the JSON object of the newly add shipping addresses user and a http status code.
     """
    # Validate that only the valid User properties from the JSON schema update_self.schema.json
    #schemas_direcotry = os.path.join(current_app.root_path, current_app.config['SCHEMA_FOLDER'])
    #schema_filepath = os.path.join(schemas_direcotry, 'del_addresses.schema.json')
