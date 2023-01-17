from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app

from openheart import db

class User(UserMixin, db.Model):

    # Unique ID of entry
    id = db.Column(db.Integer, primary_key=True)

    # Email address of user entered during registration
    email = db.Column(db.String, unique=True)

    # Hashed version of the security token sent to the user
    token_hash = db.Column(db.String())

    upload_filename_zip = db.Column(db.String(384), default="_", unique=False)
    upload_folder_zip = db.Column(db.String(384), default="_", unique=False)

    def set_token(self, token):
        self.token_hash = generate_password_hash(token)
        current_app.logger.info(f'Hash {self.token_hash} created from token.')

    def check_token(self, token):
        current_app.logger.info('Verify security token.')
        return check_password_hash(self.token_hash, token)

    def __repr__(self):
        return f"<User {self.email}>"


class File(db.Model):

    # Unique id of entry
    id = db.Column(db.Integer, primary_key=True)

    # Id of user (see above) who uploaded this file
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    name = db.Column(db.String(384), unique=False)
    name_orig = db.Column(db.String(384), default="_", unique=False)
    name_unique = db.Column(db.String(384), default="_", unique=False)

    scan_type = db.Column(db.String(384), default="_", unique=False)

    subject = db.Column(db.String(384), unique=False)
    subject_unique = db.Column(db.String(384), unique=False)

    format = db.Column(db.String(6), unique=False)

    # Status of the container
    # -1: unknown, 0: created, 1: running, 2: finishing, 3: completed, 4: failed
    container_status = db.Column(db.Integer, default=-1, nullable=False)

    # Transmitted to xnat yes/no
    transmitted = db.Column(db.Boolean, default=False, nullable=False)

    # Reconstruction finished and dicom retrieved
    reconstructed = db.Column(db.Boolean, default=False, nullable=False)

    # Submitted to the open database
    submitted = db.Column(db.Boolean, default=False, nullable=False)

    # Xnat database information about this scan
    xnat_subject_id = db.Column(db.String(384), default="_", unique=False)
    xnat_experiment_id = db.Column(db.String(384), default="_", unique=False)
    xnat_scan_id = db.Column(db.String(384), default="_", unique=False)
