from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)

from flask_mail import Message
from flask_login import current_user, login_user, logout_user

import random
from openheart import mail
from openheart.database import db, User
from openheart.utils import utils

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        current_app.logger.info(f'User {current_user.id} is already logged in.')
        return redirect(url_for('upload.upload'))

    if request.method == 'POST':
        # Get email address
        email = request.form['UserEmail']

        # Remove user token from database if email is already present
        if not User.query.filter_by(email=email).first():
            user = User(email=email)
            current_app.logger.info(f'Clear security token for user {user.id} in database.')
            user.set_token('00000')

            db.session.add(user)
            db.session.commit()

        return redirect(url_for('auth.login', email=email, err=0))

    return render_template('auth/register.html')


@bp.route('/login/<email>', methods=['POST', 'GET'])
def login(email):
    if current_user.is_authenticated:
        current_app.logger.info(f'User {current_user.id} is already logged in.')
        return redirect(url_for('upload.upload'))

    user = User.query.filter_by(email=email).first()
    if user is None:
        current_app.logger.error(f'Email address was not found in database.')
        raise AssertionError(f"Could not look up the user with email = {email}.")

    if request.method == 'GET':
        token = str(random.randrange(10000, 99999, 3))
        token = str(11111)

        user.set_token(token)
        db.session.commit()

        # Email login token
        msg = Message('Open Heart security token', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Please enter the following security token on Open Heart: {token}'
        print(msg.body)
        # mail.send(msg)

    elif request.method == 'POST':
        # Get email address
        email = request.form['UserEmail']

        user = User.query.filter_by(email=email).first()
        if user is None:
            current_app.logger.warning(f'Email address not recognised.')
            return render_template('auth/login.html', user_email=email, err=1)
        else:
            if user.check_token(request.form['UserToken']):
                login_user(user)
                current_app.logger.info(f'User {user.id} successfully logged in.')
                return redirect(url_for('upload.upload'))
            else:
                current_app.logger.warning(f'Wrong token entered for user {user.id}.')
                return render_template('auth/login.html', user_email=email, err=2)

    return render_template('auth/login.html', user_email=email, err=0)


@bp.route('/logout')
def logout():
    curr_user_id = current_user.id
    utils.clean_up_user_files()
    current_app.logger.info(f'Files for {curr_user_id} cleaned up.')

    # Logout user
    logout_user()
    current_app.logger.info(f'User {curr_user_id} logged out.')
    return redirect('/')


