from sqlalchemy.exc import IntegrityError
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
# from werkzeug.security import check_password_hash, generate_password_hash

from flask_mail import Message
from flask_login import current_user, login_user, logout_user, login_manager

from datetime import datetime

import random, os, glob
from openheart.user import db, UserModel
from openheart.utils.utils import clean_up_user_files

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('upload.upload'))

    if request.method == 'POST':
        # Get email address
        email = request.form['UserEmail']

        # Create login token
        token = str(random.randrange(10000, 99999, 3))
        token = str(11111)

        # Email login token
        msg = Message('Open Heart security token', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Please enter the following security token on Open Heart: {token}'
        print(msg.body)
        # mail.send(msg)

        # Remove user from database if email is already present
        prev_user = UserModel.query.filter_by(email=email).first()
        if prev_user:
            db.session.delete(prev_user)
            db.session.commit()

        user = UserModel(email=email)
        user.set_token(token)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('auth.login', email=email))
    return render_template('auth/register.html')


@bp.route('/login/<email>', methods=['POST', 'GET'])
def login(email):
    if current_user.is_authenticated:
        return redirect(url_for('upload.upload'))

    if request.method == 'POST':
        # Get email address
        email = request.form['UserEmail']

        # Find user and check password
        user = UserModel.query.filter_by(email=email).first()
        if user is not None and user.check_token(request.form['UserToken']):
            # Create path id for user
            time_id = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
            user_id = 'user' + str(user.id) + '_' + time_id + '_'

            # Add path id to database
            user.user_id = user_id
            db.session.commit()

            login_user(user)
            return redirect(url_for('upload.upload'))

    return render_template('login.html', user_email=email)

@bp.route('/logout')
def logout():
    clean_up_user_files()

    # Remove user from database
    cuser = UserModel.query.get(current_user.id)
    db.session.delete(cuser)
    db.session.commit()

    # Logout user
    logout_user()
    return redirect('/')

