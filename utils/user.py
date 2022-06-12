from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_mutable.types import MutablePickleType
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager
import os
 
login = LoginManager()
db = SQLAlchemy()
 
class UserModel(UserMixin, db.Model):
    __tablename__ = 'users'
 
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True)
    user_id = db.Column(db.String, unique=True)
    token_hash = db.Column(db.String())

    subjects = db.Column(MutablePickleType)
    scans = db.Column(MutablePickleType)
    xnat_subjects = db.Column(MutablePickleType)
    xnat_scans = db.Column(MutablePickleType)
    raw_data_files = db.Column(MutablePickleType)
    recon_flag = db.Column(MutablePickleType)

    def set_token(self, token):
        self.token_hash = generate_password_hash(token)
     
    def check_token(self, token):
        return check_password_hash(self.token_hash, token)

    def clear_raw_data(self):
        self.subjects = []
        self.scans = {}
        self.xnat_subjects = []
        self.xnat_scans = {}
        self.raw_data_files = {}
        self.recon_flag = {}

    def add_scan(self, subject, scan):
        if subject not in self.subjects:
            self.subjects.append(subject)
            self.scans[subject] = [scan,]
        else:
            self.scans[subject].append(scan)

    def add_xnat_scan(self, xnat_subject, xnat_scan):
        if xnat_subject not in self.xnat_subjects:
            self.xnat_subjects.append(xnat_subject)
            self.xnat_scans[xnat_subject] = [xnat_scan,]
        else:
            self.xnat_scans[xnat_subject].append(xnat_scan)

    def add_raw_data(self, subject, scan, raw_file):
        recon_flag = 0 # no images reconstructed yet
        raw_strg = subject + '_' + scan
        self.raw_data_files[raw_strg] = [raw_file, recon_flag]

    def get_raw_data(self, subject, scan):
        raw_strg = subject + '_' + scan
        return (self.raw_data_files[raw_strg][0])

    def get_recon_flag(self, subject, scan):
        raw_strg = subject + '_' + scan
        return (self.raw_data_files[raw_strg][1])

    def set_recon_flag(self, subject, scan):
        raw_strg = subject + '_' + scan
        self.raw_data_files[raw_strg][1] = 1

    def are_all_scans_reconstructed(self, subject):
        answer = True
        for scan in self.get_scans(subject):
            if self.get_recon_flag(subject, scan) == 0:
                answer = False
                break
        return(answer)

    def are_all_subjects_reconstructed(self):
        answer = True
        for subject in self.get_subjects():
            if not self.are_all_scans_reconstructed(subject):
                answer = False
                break
        return(answer)

    def get_subjects(self):
        return(self.subjects)

    def get_subject_scan_by_idx(self, subject_idx, scan_idx):
        subject = self.subjects[subject_idx]
        scan = self.get_scans(subject)[scan_idx]
        return(subject, scan)

    def get_num_subjects(self):
        return(len(self.subjects))

    def get_scans(self, subject):
        return(self.scans[subject])

    def get_num_scans(self, subject):
        return(len(self.scans[subject]))

    def get_xnat_subjects(self):
        return(self.xnat_subjects)

    def get_num_xnat_subjects(self):
        return(len(self.xnat_subjects))

    def get_xnat_scans(self, xnat_subject):
        return(self.xnat_scans[xnat_subject])

    def get_num_xnat_scans(self, xnat_subject):
        return(len(self.xnat_scans[xnat_subject]))
 
 
@login.user_loader
def load_user(id):
    return UserModel.query.get(int(id))


