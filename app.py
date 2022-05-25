from flask import Flask, request, redirect, url_for, render_template
from flask_login import login_required, current_user, login_user, logout_user
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from zipfile import ZipFile
import os, os.path, glob, random
from datetime import datetime

import sys
sys.path.append('./utils/')
import xnat_upload as xnat_up
import xnat_download as xnat_down
from user import UserModel, db, login

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

app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)


@app.before_first_request
def create_all():
    db.create_all()


@app.route('/', methods=['GET', 'POST'])
@login_required
def xnat_upload_form():
    clean_up_user_files()
    return render_template('upload.html')


@app.route('/login/<email>', methods=['POST', 'GET'])
def login(email):
    if current_user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        # Get email address
        email = request.form['UserEmail']

        # Find user and check password
        user = UserModel.query.filter_by(email=email).first()
        if user is not None and user.check_token(request.form['UserToken']):
            # Create path id for user
            time_id = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
            user_path_id = 'user' + str(user.id) + '_' + time_id + '_'

            # Add path id to database
            user.path_id = user_path_id
            db.session.commit()

            login_user(user)
            return redirect('/')

    return render_template('login.html', user_email=email)


@app.route('/register', methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect('/')

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


@app.route('/qc_check', methods=['GET', 'POST'])
@login_required
def xnat_qc_form():
    return render_template('qc_check.html')


@app.route('/uploader', methods=['POST'])
@login_required
def xnat_upload_data():
    if request.method == 'POST':
        if request.files and os.path.splitext(request.files['file'].filename)[1].lower() == '.zip':
            # Get user path id
            user = UserModel.query.get(current_user.id)
            user_path_id = user.path_id

            # Save file in upload folder
            f = request.files['file']
            f_name = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(user_path_id + f.filename))
            f.save(f_name)

            # Unzip files
            with ZipFile(f_name, 'r') as zip:
                zip_info_list = zip.infolist()
                for zip_info in zip_info_list:
                    zip_info.filename = user_path_id+zip_info.filename
                    zip.extract(zip_info, path=app.config['UPLOAD_FOLDER'])

            # Get all .h5 files with user_path_id for processing and without for display
            raw_file_list = [os.path.basename(x) for x in glob.glob(os.path.join(
                app.config['UPLOAD_FOLDER'], user_path_id) + '*.h5')]
            raw_file_list_display = [x.replace(user_path_id, '') for x in raw_file_list]

            user = UserModel.query.get(current_user.id)
            user.raw_file_list = raw_file_list
            db.session.commit()
            return render_template('upload_summary.html', files=raw_file_list_display, nfiles=len(raw_file_list_display))

    return render_template('upload.html')


@app.route('/transfer_xnat', methods=["GET", "POST"])
@login_required
def transfer_xnat():
    if request.method == "POST":
        user = UserModel.query.get(current_user.id)

        subject_list = xnat_up.upload_raw_mr(server_address, username, pw, app.config['UPLOAD_FOLDER'], user.raw_file_list, tmp_path)

        user.xnat_subject_list = subject_list
        db.session.commit()

        return render_template('qc_check.html')
    return render_template('qc_check.html')


@app.route('/qc_check_images', methods=['GET', 'POST'])
@login_required
def xnat_qc_check_images():
    reload_flag = 0
    user = UserModel.query.get(current_user.id)
    raw_files = [x.replace('.h5', '') for x in user.raw_file_list]
    qc_files = xnat_down.download_dcm_images(server_address, username, pw, user.xnat_subject_list, raw_files, tmp_path,
                                             app.config['UPLOAD_FOLDER'])

    for ind in range(len(qc_files)):
        if qc_files[ind] != -1:
            qc_files[ind] = os.path.basename(qc_files[ind])
        else:
            reload_flag = 1

    return render_template('qc_check_images.html', nfiles=len(qc_files), files=qc_files, raw_files=raw_files, reload=reload_flag)


@app.route('/submit', methods=['GET', 'POST'])
@login_required
def xnat_submit():
    if request.method == "POST":
        user = UserModel.query.get(current_user.id)

        if 'cancel' in request.form:
            return redirect('/')
        else:
            committed_files = []
            raw_file_list_display = [x.replace(user.path_id, '') for x in user.raw_file_list]
            for ind in range(len(raw_file_list_display)):
                if 'check'+str(ind) in request.form:
                    committed_files.append(raw_file_list_display[ind])
                    print('uploading file ', ind)

            clean_up_user_files()
            return render_template('thank_you.html', nfiles=len(committed_files), files=committed_files)


def clean_up_user_files():
    user = UserModel.query.get(current_user.id)
    user_path_id = user.path_id

    # Delete all files created by this user
    for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
        user_file_list = [os.path.basename(x) for x in glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], user_path_id) + '*.*')]
        for file in user_file_list:
            os.remove(os.path.join(root, file))

    return(True)


if __name__ == "__main__":
    app.run(host='localhost', port=5007, debug='on')

