from flask import Flask, request, redirect, url_for, render_template
from flask_login import login_required, current_user, login_user, logout_user
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from zipfile import ZipFile
import os, os.path, glob, random
from datetime import datetime
import shutil

import sys
sys.path.append('./utils/')
import xnat
from user import UserModel, db, login
import uuid

server_address = 'http://release.xnat.org'
username = 'admin'
pw = 'admin'

tmp_path = '/Users/christoph/Documents/KCL/XNAT/WEB_DATA/TMP/'

app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = os.path.join(os.environ.get('OH_PATH'), 'static/qc_user/')
app.config['MAX_CONTENT_PATH'] = 1e10
app.secret_key = "secret key"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///open_heart.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db.init_app(app)
login.init_app(app)
login.login_view = 'register'

app.config['MAIL_SERVER'] ='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)


@app.before_first_request
def create_all():
    db.create_all()


@app.route('/', methods=['GET'])
def welcome():
    return render_template('welcome.html')


@app.route('/tutorial_video', methods=['GET'])
def tutorial_video():
    return render_template('tutorial_video.html')


@app.route('/ismrmrd_tools', methods=['GET'])
def ismrmrd_tools():
    return render_template('ismrmrd_tools.html')


@app.route('/terms_conds', methods=['GET'])
def terms_conds():
    return render_template('terms_conds.html')


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    clean_up_user_files()
    return render_template('upload.html')


@app.route('/login/<email>', methods=['POST', 'GET'])
def login(email):
    if current_user.is_authenticated:
        return redirect('/upload')

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
            print(user_id)
            user.user_id = user_id
            db.session.commit()

            login_user(user)
            return redirect('/upload')

    return render_template('login.html', user_email=email)


@app.route('/register', methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect('/upload')

    if request.method == 'POST':
        # Get email address
        email = request.form['UserEmail']

        # Create login token
        token = str(random.randrange(10000, 99999, 3))
        token = str(11111)

        # Email login token
        msg = Message('Open Heart security token', sender=app.config['MAIL_USERNAME'], recipients=[email])
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
        return redirect(url_for('login', email=email))
    return render_template('register.html')


@app.route('/logout')
def logout():
    clean_up_user_files()

    # Remove user from database
    user = UserModel.query.get(current_user.id)
    db.session.delete(user)
    db.session.commit()

    # Logout user
    logout_user()
    return redirect('/')


@app.route('/uploader', methods=['POST'])
@login_required
def uploader():
    if request.method == 'POST':
        if request.files and os.path.splitext(request.files['file'].filename)[1].lower() == '.zip':
            # Get user path id
            user = UserModel.query.get(current_user.id)

            # Save file in upload folder
            f = request.files['file']
            f_name = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(user.user_id + f.filename))
            f.save(f_name)

            # Get info from database
            user = UserModel.query.get(current_user.id)

            # Unzip files
            with ZipFile(f_name, 'r') as zip:
                zip_info_list = zip.infolist()
                # Go through list of files and folders and check for h5 files
                for zip_info in zip_info_list:
                    if not zip_info.is_dir():
                        cpath, cfile = os.path.split(zip_info.filename)
                        if os.path.splitext(cfile)[1] == '.h5':
                            user.add_scan(cpath, cfile)
                            cfile_name = str(uuid.uuid4())
                            user.add_raw_data(cpath, cfile, cfile_name)
                            zip_info.filename = cfile_name + '.h5'
                            zip.extract(zip_info, path=app.config['UPLOAD_FOLDER'])

            db.session.commit()
            return render_template('upload_summary.html', cuser=user)

    return render_template('upload.html')


@app.route('/check', methods=["GET", "POST"])
@login_required
def check():
    if request.method == "POST":
        user = UserModel.query.get(current_user.id)
        user = xnat.upload_raw_mr(server_address, username, pw, app.config['UPLOAD_FOLDER'], user, tmp_path)
        db.session.commit()

        return render_template('check.html')
    return render_template('check.html')


@app.route('/check_images', methods=['GET', 'POST'])
@login_required
def check_images():
    user = UserModel.query.get(current_user.id)
    user = xnat.download_dcm_images(server_address, username, pw, user, tmp_path, app.config['UPLOAD_FOLDER'])
    db.session.commit()
    return render_template('check_images.html', cuser=user, reload=(user.are_all_subjects_reconstructed()==False))


@app.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == "POST":
        user = UserModel.query.get(current_user.id)

        if 'cancel' in request.form:
            return redirect('/upload')
        else:
            commit_subjects = []
            delete_subjects = []
            for ind in range(user.get_num_xnat_subjects()):
                if 'check'+str(ind) in request.form:
                    commit_subjects.append(user.get_xnat_subjects()[ind])
                else:
                    delete_subjects.append(user.get_xnat_subjects()[ind])

            xnat.commit_to_open(server_address, username, pw, commit_subjects)
            xnat.delete_from_vault(server_address, username, pw, delete_subjects)
            clean_up_user_files()
            return render_template('thank_you.html', cuser=user, subjects=commit_subjects, num_subjects=len(commit_subjects))


def clean_up_user_files():
    user = UserModel.query.get(current_user.id)
    user_id = user.user_id

    # Path where all files are saved
    cpath = app.config['UPLOAD_FOLDER']

    # Delete zip file starting with user.user_id
    f_zip = glob.glob(os.path.join(cpath, user_id + '*.zip'))
    if len(f_zip) > 0:
        os.remove(f_zip[0])

    # Delete all files created by user
    for subject in user.get_subjects():
        for scan in user.get_scans(subject):
            # Get unique filename without file ending
            cfile = user.get_raw_data(subject, scan)

            # Remove the raw data file
            if os.path.exists(os.path.join(cpath, cfile + '.h5')):
                os.remove(os.path.join(cpath, cfile + '.h5'))

            # Remove the (animated) gif file
            if os.path.exists(os.path.join(cpath, cfile + '.gif')):
                os.remove(os.path.join(cpath, cfile + '.gif'))

    return(True)


if __name__ == "__main__":
    app.run(host='localhost', port=5001, debug='on')
