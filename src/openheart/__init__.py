import logging
import os
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# this must be imported after db is created s.t. the database can pick up the tables form this file
from openheart.user import UserModel 


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        # SQLALCHEMY_DATABASE_URI = 'sqlite:////db/open_heart.db'
        SQLALCHEMY_DATABASE_URI = 'sqlite:///open_heart.db',
        MAIL_SERVER ='smtp.gmail.com',
        MAIL_PORT = 465,
        MAIL_USERNAME = os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD'),
        DATA_FOLDER='/data/',
        TEMP_FOLDER='/temp/',
        XNAT_SERVER=os.environ.get('XNAT_SERVER'),
        XNAT_ADMIN_USER=os.environ.get('XNAT_ADMIN_USER'),
        XNAT_ADMIN_PW=os.environ.get('XNAT_ADMIN_PW'),
        XNAT_PROJECT_ID_VAULT=os.environ.get('XNAT_PROJECT_ID_VAULT'),
        XNAT_PROJECT_ID_OPEN=os.environ.get('XNAT_PROJECT_ID_OPEN'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
        # logging.basicConfig(filename='/logs/development.log', level=logging.DEBUG)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)
        

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/', methods=['GET'])
    def welcome():
        return redirect(url_for('home.welcome'))

    mail = Mail()
    mail.init_app(app)

    # initialize the database onto the app
    db.init_app(app)

    with app.app_context():
        db.create_all()

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(userid):
        return UserModel.query.get(userid)

    from . import home
    app.register_blueprint(home.bp)

    from . import auth
    app.register_blueprint(auth.bp)

    from . import upload 
    app.register_blueprint(upload.bp)

    # from . import blog
    # app.register_blueprint(blog.bp)
    # app.add_url_rule('/', endpoint='index')

    return app
