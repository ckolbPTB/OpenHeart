from sqlalchemy.exc import IntegrityError
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
# from werkzeug.security import check_password_hash, generate_password_hash

from flask_mail import Message
from flask_login import current_user, login_user, logout_user

from datetime import datetime

import random
from openheart import mail
from openheart.database import db, User
from openheart.utils import utils

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('upload.upload'))

    if request.method == 'POST':
        # Get email address
        email = request.form['UserEmail']

        # Remove user from database if email is already present
        if not User.query.filter_by(email=email).first():

            user = User(email=email)
            user.set_token('00000')

            db.session.add(user)
            db.session.commit()

        return redirect(url_for('auth.login', email=email))

    return render_template('auth/register.html')


@bp.route('/login/<email>', methods=['POST', 'GET'])
def login(email):
    if current_user.is_authenticated:
        return redirect(url_for('upload.upload'))

    user = User.query.filter_by(email=email).first()
    if user is None:
        raise AssertionError(f"Could not look up the user with email = {email}.")

    token = str(random.randrange(10000, 99999, 3))
    token = str(11111)

    user.set_token(token)
    db.session.commit()

    # Email login token
    msg = Message('Open Heart security token', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
    msg.body = f'Please enter the following security token on Open Heart: {token}'
    print(msg.body)
    # mail.send(msg)

    if request.method == 'POST':
        # Get email address
        email = request.form['UserEmail']

        user = User.query.filter_by(email=email).first()
        if user is not None:
            if user.check_token(request.form['UserToken']):
                login_user(user)
                return redirect(url_for('upload.upload'))
            else:
                flash("Wrong Token.")

    return render_template('auth/login.html', user_email=email)

@bp.route('/logout')
def logout():
    utils.clean_up_user_files()

    # Logout user
    logout_user()
    return redirect('/')


