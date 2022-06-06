from flask import Flask, request, redirect, url_for, render_template
from flask_login import login_required, current_user, login_user, logout_user
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from zipfile import ZipFile
import os, os.path, glob, random
from datetime import datetime

import sys
sys.path.append('./utils/')
import xnat
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
            user_path_id = 'user' + str(user.id) + '_' + time_id + '_'

            # Add path id to database
            user.path_id = user_path_id
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

            # Get all the subfolders in the extracted archive which represent different subjects
            subject_folders = [d for d in os.listdir(os.path.join(app.config['UPLOAD_FOLDER'])) if
                               os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], d))]
            subject_folders_display = [x.replace(user_path_id, '') for x in subject_folders]

            # Create dictionary with the raw data files of each subject
            subject_list = []
            subject_list_display = []
            for ind in range(len(subject_folders)):
                # Get all .h5 files in this folder
                clist = [os.path.basename(x) for x in glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], subject_folders[ind], '*.h5'))]
                clist_display = [x.replace(user_path_id, '') for x in clist]

                # Create a list for each subject with [subject name, number of files, raw data filenames]
                clist.insert(0, len(clist))
                clist.insert(0, subject_folders[ind])
                subject_list.append(clist)

                clist_display.insert(0, len(clist_display))
                clist_display.insert(0, subject_folders_display[ind])
                subject_list_display.append(clist_display)

            user = UserModel.query.get(current_user.id)
            user.subject_list = subject_list
            user.subject_list_display = subject_list_display
            db.session.commit()
            return render_template('upload_summary.html', files=subject_list_display, nfiles=len(subject_list_display))

    return render_template('upload.html')


@app.route('/check', methods=["GET", "POST"])
@login_required
def check():
    if request.method == "POST":
        user = UserModel.query.get(current_user.id)

        xnat_subject_list = xnat.upload_raw_mr(server_address, username, pw, app.config['UPLOAD_FOLDER'], user.subject_list, tmp_path)

        user.xnat_subject_list = xnat_subject_list
        db.session.commit()

        return render_template('check.html')
    return render_template('check.html')


@app.route('/check_images', methods=['GET', 'POST'])
@login_required
def check_images():
    reload_flag = 0
    user = UserModel.query.get(current_user.id)
    check_files = xnat.download_dcm_images(server_address, username, pw, user.xnat_subject_list, user.subject_list,
                                           tmp_path, app.config['UPLOAD_FOLDER'])

    raw_files_html = []
    check_files_html = []
    for ind in range(len(check_files)):
        for snd in range(len(check_files[ind])):
            if check_files[ind][snd] != -1:
                check_files_html.append(os.path.basename(check_files[ind][snd]))
            else:
                check_files_html.append(-1)
                reload_flag = 1
            raw_files_html.append(user.xnat_subject_list_display[ind][snd+2])

    return render_template('check_images.html', nfiles=len(check_files_html), files=check_files_html,
                           raw_files=raw_files_html, reload=reload_flag)


@app.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == "POST":
        user = UserModel.query.get(current_user.id)

        if 'cancel' in request.form:
            return redirect('/upload')
        else:
            commit_files = []
            commit_subjects = []
            delete_subjects = []
            raw_file_list_display = [x.replace(user.path_id, '') for x in user.raw_file_list]
            for ind in range(len(raw_file_list_display)):
                if 'check'+str(ind) in request.form:
                    commit_files.append(raw_file_list_display[ind])
                    commit_subjects.append(user.xnat_subject_list[ind])
                else:
                    delete_subjects.append(user.xnat_subject_list[ind])

            xnat.commit_to_open(server_address, username, pw, commit_subjects)
            xnat.delete_from_vault(server_address, username, pw, delete_subjects)
            clean_up_user_files()
            return render_template('thank_you.html', nfiles=len(commit_files), files=commit_files)


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
