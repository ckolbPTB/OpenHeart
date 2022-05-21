from flask import Flask, flash, request, redirect, url_for, render_template, make_response
from flask_login import login_required, current_user, login_user, logout_user
from flask_mail import Mail, Message
from models import UserModel, db, login
from werkzeug.utils import secure_filename
from zipfile import ZipFile
import os, os.path, shutil, glob, random

import sys
sys.path.append('./utils/')
import utils
import xnat_upload as xnat_up
import xnat_download as xnat_down

server_address = 'http://release.xnat.org'
username = 'admin'
pw = 'admin'

main_path = os.environ.get('XNAT_MPATH')
data_path = main_path + 'unzip/'
tmp_path_up = main_path + 'upload/'
tmp_path_down = main_path + 'download/'
qc_im_path = main_path + 'qc/'
qc_im_path = '/Users/christoph/Documents/KCL/Matlab/Bitbucket/ck/Xnat/static/'


app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = data_path
app.config['MAX_CONTENT_PATH'] = 1e10
app.secret_key = "secret key"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login.init_app(app)
login.login_view = 'register'

app.config['UPLOAD_FOLDER'] = data_path

app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)

ALLOWED_EXTENSIONS = set(['h5',])

FNAMES_H5 = []
SUBJECT_LIST = []


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.before_first_request
def create_all():
    db.create_all()


@app.route('/', methods=['GET', 'POST'])
@login_required
def xnat_upload_form():
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

        user = UserModel(email=email)
        user.set_token(token)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login', email=email))
    return render_template('register.html')


@app.route('/logout')
def logout():
    # Remove user from database
    user = UserModel.query.get(current_user.id)
    db.session.delete(user)
    db.session.commit()

    # Logout user
    logout_user()
    return redirect('/')


@app.route('/qc_check_images', methods=['GET', 'POST'])
@login_required
def xnat_qc_check_images():
    fname_qc = [x.replace('.h5', '') for x in FNAMES_H5]
    qc_files = xnat_down.download_dcm_images(server_address, username, pw, SUBJECT_LIST, fname_qc, tmp_path_down, qc_im_path)
    for ind in range(len(qc_files)):
        if qc_files[ind] != -1:
            qc_files[ind] = os.path.basename(qc_files[ind])

    print(qc_files)
    return render_template('qc_check_images.html', nfiles=len(qc_files), files=qc_files)


@app.route('/qc_check', methods=['GET', 'POST'])
@login_required
def xnat_qc_form():
    return render_template('qc_check.html')


@app.route('/uploader', methods=['POST'])
@login_required
def xnat_upload_data():
    if request.method == 'POST':
        if request.files:
            global FNAMES_H5
            # Save file in upload folder
            f = request.files['file']
            f_name = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename))
            f.save(f_name)

            # Unzip files
            with ZipFile(f_name, 'r') as zip:
                zip.extractall(app.config['UPLOAD_FOLDER'])

            # Get all .h5 files
            FNAMES_H5 = [os.path.basename(x) for x in glob.glob(app.config['UPLOAD_FOLDER'] + '/*.h5')]

            return render_template('upload_summary.html', files=FNAMES_H5, nfiles=len(FNAMES_H5))

    return render_template('upload.html')


@app.route('/transfer_xnat', methods=["GET", "POST"])
@login_required
def transfer_xnat():
    if request.method == "POST":
        global SUBJECT_LIST

        SUBJECT_LIST = xnat_up.upload_raw_mr(server_address, username, pw, data_path, tmp_path_up)

        # Delete all files in the tmp folder
        for root, dirs, files in os.walk(data_path):
            for file in files:
                os.remove(os.path.join(root, file))
        return render_template('qc_check.html')


if __name__ == "__main__":
    app.run(host='localhost', port=5000, debug='on')

