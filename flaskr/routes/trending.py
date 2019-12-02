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
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import or_
from flaskr.db import session_scope
from flaskr.models.Order import Order, OrderLine, OrderStatus
from flaskr.models.Cart import Cart, CartLine
from flaskr.models.User import User
from flaskr.models.Product import Product
from flaskr.models.Review import Review

from flaskr.email import send
from flaskr.routes.utils import login_required, not_login, cross_origin, is_logged_in, admin_required
from datetime import datetime, timedelta
from flaskr.routes.users import viewreview
from flaskr.models.ProductRecord import ProductRecord

bp = Blueprint('trending', __name__, url_prefix='/trending')


@bp.route('', methods=['GET', 'OPTIONS'])
@cross_origin(methods=['GET'])
def view_trending_by_week():
        # Later will add the ability to sort by date and Category
        """Endpoint use to compute the total number of items sold between two dates.

             Returns:
                 (str, int) -- Returns a string with the number of sales.
             """
        try:
            with session_scope() as db_session:
                # Added filters by date
                end_date = datetime.today()
                n = 7
                week = (end_date - timedelta(days=n)).date()
                users = db_session.query(User).all()
                trending = []
                for user in users:
                    username = user.username
                    my_rev = viewreview(username)
                    score = float(my_rev.json['score'])

                    #score 0 means unreviewed seller
                    if score >= 3.5 or score == 0:
                        products = db_session.query(Product).filter(Product.user_id == user.id).all()
                        for product in products:
                            product_permalink = product.permalink
                            sales = 0
                            order_lines = db_session.query(OrderLine).filter(OrderLine.product_id == product.id, Order.date.between(week, end_date))
                            for order_line in order_lines:
                                sales = sales + order_line.quantity
                            product = ProductRecord(product_permalink, sales)
                            trending.append(product)
                    #Sort the entries
                    trending.sort(reverse=True)
                    first_ten = []
                    for i in range(min(10,len(trending))):
                        first_ten.append(trending[i].to_json())

        except DBAPIError as db_error:
            # Returns an error in case of a integrity constraint not being followed.
            return {
                       'code': 400,
                       'message': re.search('DETAIL: (.*)', db_error.args[0]).group(1)
                   }, 400
        except NoResultFound:
            # Returns an error in case of a integrity constraint not being followed.
            return {
                       'code': 400,
                       'message': "No sales have been registered"
                   }, 400
        return{
            "top_products": first_ten
              }, 200
