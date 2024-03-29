import logging
from logging.config import dictConfig
import os
from flask import Flask, redirect, url_for, g, render_template
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import HTTPException

db = SQLAlchemy()
mail = Mail()

# Debug settings
oh_debug = os.environ.get("OH_DEBUG").lower() == 'true'

# This must be imported after db is created s.t. the database can pick up the tables form this file
from openheart.database import User
import openheart.logger as logger

def create_app(test_config=None):
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        SQLALCHEMY_DATABASE_URI='sqlite:///' + os.environ.get('OH_DATA_PATH') + '/db/open_heart.db',
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=465,
        MAIL_USE_TSL=False,
        MAIL_USE_SSL=True,
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        DATA_FOLDER=os.environ.get('OH_DATA_PATH')+'/data/',
        XNAT_SERVER=os.environ.get('XNAT_SERVER'),
        XNAT_ADMIN_USER=os.environ.get('XNAT_ADMIN_USER'),
        XNAT_ADMIN_PW=os.environ.get('XNAT_ADMIN_PW'),
        XNAT_PROJECT_ID_VAULT=os.environ.get('XNAT_PROJECT_ID_VAULT'),
        XNAT_PROJECT_ID_OPEN=os.environ.get('XNAT_PROJECT_ID_OPEN'),
        OH_APP_PATH=os.environ.get('OH_APP_PATH'),
        MAX_CONTENT_LENGTH=int(os.environ.get('OH_APP_MAX_FILE_SIZE')),
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
        dictConfig(logger.log_dict_config)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    mail.init_app(app)

    # Initialize the database onto the app
    db.init_app(app)

    with app.app_context():
        db.create_all()

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(userid):
        return User.query.get(userid)

    if not oh_debug:
        @app.errorhandler(Exception)
        def error_handler(e):
            app.logger.error(f'The following error occured: {e}', exc_info=True)
            if isinstance(e, HTTPException):
                return render_template("error/error.html", e=e)

            # Handle non-HTTP exceptions only
            return render_template("error/error.html", e=e), 500

    from . import home
    app.register_blueprint(home.bp)

    from . import auth
    app.register_blueprint(auth.bp)

    from . import upload 
    app.register_blueprint(upload.bp)

    # Start page
    @app.route('/', methods=['GET'])
    def welcome():
        return redirect(url_for('home.welcome'))

    return app
