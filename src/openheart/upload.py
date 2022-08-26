from flask import (
    Blueprint, render_template, request, current_app, redirect, url_for, flash, g)
from flask_login import login_required, current_user

from werkzeug.utils import secure_filename
from zipfile import ZipFile

from datetime import datetime
import os, sys
from pathlib import Path

from openheart.utils import xnat
from openheart.utils import utils
from openheart.user import db, User, File

bp = Blueprint('upload', __name__, url_prefix='/upload')

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    utils.clean_up_user_files()
    return render_template('upload/upload.html')


@bp.route('/uploader', methods=['POST'])
@login_required
def uploader():
    if request.method == 'POST':
        time_id = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]

        if request.files and os.path.splitext(request.files['file'].filename)[1].lower() == '.zip':
            # Get info from database
            user = User.query.get(current_user.id)

            # Save file in upload folder
            f = request.files['file']
            filepath_out = Path(current_app.config['DATA_FOLDER'])
            f_name =filepath_out / secure_filename(f"{user.id}_{f.filename}")
            f.save(str(f_name))

            # Unzip files
            with ZipFile(f_name, 'r') as zip:
                zip_info_list = zip.infolist()
                # Go through list of files and folders and check for h5 files
                for zip_info in zip_info_list:
                    if not zip_info.is_dir():
                        czip_content = Path(zip_info.filename)
                        cpath, cfile = czip_content.parent, czip_content.name 

                        if utils.valid_extension(czip_content):

                            fname_out = filepath_out / cfile
                            zip_info.filename = str(cfile)
                            zip.extract(zip_info, path=filepath_out)

                            subject_timed = f"Subj-{str(cpath)}-{time_id}"
                            file = File(user_id=current_user.id, 
                                        name = str(fname_out),
                                        name_unique="_", 
                                        subject=str(cpath),
                                        subject_unique = subject_timed,
                                        format = czip_content.suffix)

                            db.session.add(file)
                db.session.commit()
            postprocess_upload()

            list_files = File.query.filter_by(user_id=current_user.id, format='.h5', 
                                              transmitted=False, reconstructed=False).all()

            return render_template('upload/upload_summary.html', list_files=list_files)

    return render_template('upload/upload.html')

def postprocess_upload():
    assert convert_files(), "The conversion of some files failed."
    assert uniquely_identify_files(), "The renaming into md5 hashs failed."

@login_required
def convert_files():
    list_files = File.query.filter_by(user_id=current_user.id, format='.dat', 
                                      transmitted=False, reconstructed=False).all()

    for file in list_files:
        fname_out = utils.convert_dat_file(file.name)
        file = File(file)
        file.name=fname_out
        file.format='.h5'

        db.session.add(file)

    db.session.commit()

    return True

def uniquely_identify_files():

    list_files = File.query.filter_by(user_id=current_user.id,
                                      name_unique = "_",
                                      format='.h5', 
                                      transmitted=False, reconstructed=False).all()

    for file in list_files:
        md5_identifier = utils.rename_h5_file(Path(file.name))
        file.name_unique = str(md5_identifier)
        db.session.commit()

    return True


@bp.route('/check', methods=["GET", "POST"])
@login_required
def check():
    if request.method == "POST":
        list_files = File.query.filter_by(user_id=current_user.id, format='.h5', 
                                          transmitted=False).all()

        success = xnat.upload_raw_mr(list_files,
                                    current_app.config['XNAT_SERVER'], current_app.config['XNAT_ADMIN_USER'],
                                    current_app.config['XNAT_ADMIN_PW'], current_app.config['XNAT_PROJECT_ID_VAULT'])
        current_app.logger.info(f"Finished upload request to {current_app.config['XNAT_PROJECT_ID_VAULT']}.")

        if success:
            for f in list_files:
                f.transmitted = True
        else:
            raise AssertionError(f"Something with thte xnat upload went wrong.")

        db.session.commit()

        return render_template('upload/check.html')
    return render_template('upload/check.html')





@bp.route('/check_images', methods=['GET', 'POST'])
@login_required
def check_images():
    user = User.query.get(current_user.id)
    user = xnat.download_dcm_images(current_app.config['XNAT_SERVER'], current_app.config['XNAT_ADMIN_USER'],
                                    current_app.config['XNAT_ADMIN_PW'], current_app.config['XNAT_PROJECT_ID_VAULT'], user, 
                                    current_app.config['TEMP_FOLDER'], current_app.config['DATA_FOLDER'])
    db.session.commit()
    print('are_all_reconstructed ', user.are_all_subjects_reconstructed())
    print('reload ', user.are_all_subjects_reconstructed()==False)
    return render_template('upload/check_images.html', cuser=user, reload=(user.are_all_subjects_reconstructed()==False))


@bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == "POST":
        user = User.query.get(current_user.id)

        if 'cancel' in request.form:
            return redirect(url_for('upload.upload'))
        else:
            commit_subjects = []
            commit_xnat_subjects = []
            delete_xnat_subjects = []
            for ind in range(user.get_num_xnat_subjects()):
                if 'check'+str(ind) in request.form:
                    commit_xnat_subjects.append(user.get_xnat_subjects()[ind])
                    commit_subjects.append(user.get_subjects()[ind])
                else:
                    delete_xnat_subjects.append(user.get_xnat_subjects()[ind])

            xnat.commit_to_open(current_app.config['XNAT_SERVER'], current_app.config['XNAT_ADMIN_USER'], current_app.config['XNAT_ADMIN_PW'],
                                current_app.config['XNAT_PROJECT_ID_VAULT'], current_app.config['XNAT_PROJECT_ID_OPEN'], commit_xnat_subjects)
            xnat.delete_from_vault(current_app.config['XNAT_SERVER'], current_app.config['XNAT_ADMIN_USER'],
                                   current_app.config['XNAT_ADMIN_PW'], current_app.config['XNAT_PROJECT_ID_VAULT'],
                                   delete_xnat_subjects)
            return render_template('home/thank_you.html', cuser=user, subjects=commit_subjects, num_subjects=len(commit_subjects))
