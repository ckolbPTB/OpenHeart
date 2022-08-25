from flask import (
    Blueprint, render_template, request, current_app, redirect, url_for)
from flask_login import login_required, current_user

from werkzeug.utils import secure_filename
from zipfile import ZipFile

import os
from pathlib import Path

from openheart.utils import xnat
from openheart.utils import utils
from openheart.user import db, UserModel

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
        if request.files and os.path.splitext(request.files['file'].filename)[1].lower() == '.zip':
            # Get info from database
            user = UserModel.query.get(current_user.id)

            # Save file in upload folder
            f = request.files['file']
            f_name = os.path.join(current_app.config['DATA_FOLDER'], secure_filename(user.user_id + f.filename))
            f.save(f_name)

            filepath_out = Path(current_app.config['DATA_FOLDER'])
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

                            if czip_content.suffix == '.dat':
                                fname_out = utils.convert_dat_file(fname_out)

                            cfile_name = utils.rename_h5_file(fname_out)
                            user.add_scan(str(cpath), str(cfile))
                            user.add_raw_data(str(cpath), str(cfile), cfile_name.stem)

            db.session.commit()
            return render_template('upload/upload_summary.html', cuser=user)

    return render_template('upload/upload.html')




@bp.route('/check', methods=["GET", "POST"])
@login_required
def check():
    if request.method == "POST":
        user = UserModel.query.get(current_user.id)
        user = xnat.upload_raw_mr(current_app.config['XNAT_SERVER'], current_app.config['XNAT_ADMIN_USER'], current_app.config['XNAT_ADMIN_PW'],
                                  current_app.config['DATA_FOLDER'], current_app.config['XNAT_PROJECT_ID_VAULT'], user, current_app.config['TEMP_FOLDER'])
        db.session.commit()

        return render_template('upload/check.html')
    return render_template('upload/check.html')





@bp.route('/check_images', methods=['GET', 'POST'])
@login_required
def check_images():
    user = UserModel.query.get(current_user.id)
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
        user = UserModel.query.get(current_user.id)

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


