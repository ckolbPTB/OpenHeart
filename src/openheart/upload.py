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
from openheart.database import db, User, File

bp = Blueprint('upload', __name__, url_prefix='/upload')


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    utils.clean_up_user_files(recreate_user_folders=True)
    return render_template('upload/upload.html')


@bp.route('/uploader', methods=['POST'])
@login_required
def uploader():
    if request.method == 'POST':
        time_id = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]

        if request.files and os.path.splitext(request.files['file'].filename)[1].lower() == '.zip':
            # Get info from database
            user = User.query.get(current_user.id)
            user_folder = 'Uid' + str(current_user.id)

            # Save file in upload folder
            f = request.files['file']
            filepath_out = Path(current_app.config['DATA_FOLDER']) / user_folder
            f_name = filepath_out / secure_filename(f"{user.id}_{f.filename}")
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

                            fname_out = f"user_{current_user.id}_subj_{cpath}_{cfile}"
                            zip_info.filename = str(fname_out)
                            zip.extract(zip_info, path=filepath_out)

                            subject_timed = f"Subj-{str(cpath)}-{time_id}"
                            file = File(user_id=current_user.id, 
                                        name=str(filepath_out / fname_out),
                                        name_orig=str(cfile),
                                        name_unique="_", 
                                        subject=str(cpath),
                                        subject_unique=subject_timed,
                                        format=czip_content.suffix)

                            db.session.add(file)
                db.session.commit()

            # Remove zip file
            os.remove(str(f_name))

            # Transform .dat to .h5 and rename .h5 with unique uid
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

        success = xnat.upload_raw_mr_to_vault(list_files)
        current_app.logger.info(f"Finished upload request to {current_app.config['XNAT_PROJECT_ID_VAULT']}.")

        if success:
            for f in list_files:
                current_app.logger.info(f"Finished upload request to {f.xnat_subject_id}.")
                current_app.logger.info(f"Finished upload request to {f.xnat_experiment_id}.")
                current_app.logger.info(f"Finished upload request to {f.xnat_scan_id}.")
        else:
            raise AssertionError(f"Something with the xnat upload went wrong.")

        db.session.commit()

        return render_template('upload/check.html')
    return render_template('upload/check.html')


@bp.route('/check_images', methods=['GET', 'POST'])
@login_required
def check_images():

    files = File.query.filter_by(user_id=current_user.id, format='.h5', 
                                 transmitted=True, submitted=False).all()

    files = xnat.download_dcm_images(files)
    db.session.commit()

    all_recons_performed = True
    for f in files:
        all_recons_performed *= f.reconstructed

    subject_file_lut = utils.create_subject_file_lookup(files)

    current_app.logger.info(f"We will try to render {list(subject_file_lut.keys())} and {subject_file_lut}.")
    return render_template('upload/check_images.html', subjects=list(subject_file_lut.keys()),
                           files_for_subject=subject_file_lut, reload=(all_recons_performed == False))



@bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == "POST":
        if 'cancel' in request.form:
            return redirect(url_for('upload.upload'))
        else:

            list_files = File.query.filter_by(user_id=current_user.id, format='.h5', transmitted=True,
                                              reconstructed=True, submitted=False).all()

            files_rejected = []
            for f in list_files:
                if 'check_'+str(f.subject) not in request.form:
                    files_rejected.append(f)

            xnat.delete_scans_from_vault(files_rejected)
            for f in files_rejected:
                db.session.delete(f)

            db.session.commit()

            list_files = File.query.filter_by(user_id=current_user.id, format='.h5', transmitted=True,
                                              reconstructed=True, submitted=False).all()
            files_accepted = []
            for f in list_files:
                if 'check_'+str(f.subject) in request.form:
                    files_accepted.append(f)

            # Add snapshots
            xnat.add_snapshot_images(files_accepted)

            # Commit subjects to open project
            xnat.commit_subjects_to_open(files_accepted)

            for f in files_accepted:
                f.submitted = True

            db.session.commit()

        return render_template('home/thank_you.html', submitted_files=list_files)
