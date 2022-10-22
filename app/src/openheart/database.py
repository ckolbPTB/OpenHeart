from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app

from openheart import db

class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True)
    token_hash = db.Column(db.String())

    def set_token(self, token):
        self.token_hash = generate_password_hash(token)
        current_app.logger.info(f'Hash {self.token_hash} created from token.')

    def check_token(self, token):
        current_app.logger.info('Verify security token.')
        return check_password_hash(self.token_hash, token)

    def __repr__(self):
        return f"<User {self.email}>"

class File(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    name = db.Column(db.String(384), unique=False)
    name_orig = db.Column(db.String(384), default="_", unique=False)
    name_unique = db.Column(db.String(384), default="_", unique=False)

    scan_type = db.Column(db.String(384), default="_", unique=False)

    subject = db.Column(db.String(384), unique=False)
    subject_unique = db.Column(db.String(384), unique=False)

    format = db.Column(db.String(6), unique=False)
    transmitted = db.Column(db.Boolean, default=False, nullable=False)

    reconstructed = db.Column(db.Boolean, default=False, nullable=False)
    submitted = db.Column(db.Boolean, default=False, nullable=False)

    xnat_subject_id = db.Column(db.String(384), default="_", unique=False)
    xnat_experiment_id = db.Column(db.String(384), default="_", unique=False)
    xnat_scan_id = db.Column(db.String(384), default="_", unique=False)
