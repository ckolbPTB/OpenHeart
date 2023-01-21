from flask import Blueprint, render_template, request, current_app, redirect, url_for, jsonify, abort, Response
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
    return render_template('upload/upload.html',
                           max_file_size=str(int(current_app.config['MAX_CONTENT_LENGTH']/(1024 * 1024 * 1024))))


@bp.route('/uploader', methods=['POST'])
@login_required
def uploader():
    if request.method == 'POST':
        # Get info from database
        user = User.query.get(current_user.id)
        user_folder = 'Uid' + str(current_user.id)
        current_app.logger.info(f'Current user {current_user.id} with folder {user_folder}.')

        # Save file in upload folder
        f = request.files['file']
        filepath_out = Path(current_app.config['DATA_FOLDER']) / user_folder
        f_name = filepath_out / secure_filename(f"{user.id}_{f.filename}")
        f.save(str(f_name))
        current_app.logger.info(f'File {f_name} saved.')

        current_user.upload_filename_zip = str(f_name)
        current_user.upload_folder_zip = user_folder
        db.session.commit()

    return render_template('upload/upload.html',
                           max_file_size=str(int(current_app.config['MAX_CONTENT_LENGTH']/(1024 * 1024 * 1024))))


@bp.route('/unpack', methods=['POST'])
@login_required
def unpack():
    if request.method == 'POST':
        # Get folder and file names
        f_name = current_user.upload_filename_zip
        user_folder = current_user.upload_folder_zip

        print(f_name)
        print(user_folder)

        if f_name != '_' and user_folder != '_':
            time_id = datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S-%f')[:-3]
            current_app.logger.info(f'Current time ID created: {time_id}.')

            filepath_out = Path(current_app.config['DATA_FOLDER']) / user_folder

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
                            current_app.logger.info(f'File {zip_info.filename} extracted to {filepath_out}.')

                            # Get scan type from filename
                            scan_type = utils.get_scan_type(cfile)
                            subject_timed = f"Subj-{str(cpath)}-{time_id}"
                            file = File(user_id=current_user.id, name=str(filepath_out / fname_out),
                                        name_orig=str(cfile), name_unique="_", subject=str(cpath),
                                        subject_unique=subject_timed, format=czip_content.suffix,
                                        scan_type=scan_type)
                            current_app.logger.info('File entry created:')
                            current_app.logger.info(f'   user_id: {file.user_id}')
                            current_app.logger.info(f'   name: {file.name}')
                            current_app.logger.info(f'   name_orig: {file.name_orig}')
                            current_app.logger.info(f'   name_unique: {file.name_unique}')
                            current_app.logger.info(f'   subject: {file.subject}')
                            current_app.logger.info(f'   subject_unique: {file.subject_unique}')
                            current_app.logger.info(f'   format: {file.format}')
                            current_app.logger.info(f'   scan_type: {file.scan_type}')

                            db.session.add(file)
                db.session.commit()

            # Remove zip file
            os.remove(str(f_name))
            current_app.logger.info(f'File {f_name} removed.')

            current_user.upload_filename_zip = "_"
            current_user.upload_folder_zip = "_"
            db.session.commit()

            # Transform .dat to .h5
            assert convert_files(), "The conversion of some files failed."

            # Verify uniqueness of files and rename .h5 with unique uid
            list_duplicate_files = uniquely_identify_files()

            files = File.query.filter_by(user_id=current_user.id, format='.h5', transmitted=False,
                                         reconstructed=False).all()
            subject_file_lut = utils.create_subject_file_lookup(files)

            return render_template('upload/upload_summary.html', subjects=list(subject_file_lut.keys()),
                                   files_for_subject=subject_file_lut, scan_type_list=list(utils.scan_types.keys()),
                                   list_duplicate_files=list_duplicate_files)

    return render_template('upload/upload.html',
                           max_file_size=str(int(current_app.config['MAX_CONTENT_LENGTH']/(1024 * 1024 * 1024))))


@login_required
def convert_files():
    list_files = File.query.filter_by(user_id=current_user.id, format='.dat', transmitted=False,
                                      reconstructed=False).all()

    for file in list_files:
        fname_out = utils.convert_dat_file(file.name)
        current_app.logger.info(f'File {file.name} converted to {fname_out}.')

        file = File(file)
        file.name = fname_out
        file.format = '.h5'

        db.session.add(file)
    db.session.commit()

    return True


def uniquely_identify_files():
    list_files = File.query.filter_by(user_id=current_user.id, name_unique="_", format='.h5', transmitted=False,
                                      reconstructed=False).all()

    list_unique_names = []
    list_duplicate_files = []
    for f in list_files:
        md5_identifier = str(utils.rename_h5_file(Path(f.name)))
        if md5_identifier in list_unique_names:
            current_app.logger.warning(f'File {f.name} is a duplicate and will be removed.')
            db.session.delete(f)
            list_duplicate_files.append(f'Subject {f.subject} - Scan {f.name_orig}')
        else:
            f.name_unique = md5_identifier
            current_app.logger.info(f'Unique filename {f.name_unique} for file {f.name} added.')
            list_unique_names.append(md5_identifier)
    db.session.commit()

    return list_duplicate_files


@bp.route('/upload_xnat', methods=["POST"])
@login_required
def upload_xnat():
    if request.method == "POST":
        if 'cancel' in request.form:
            return redirect(url_for('upload.upload'))
        else:
            list_files = File.query.filter_by(user_id=current_user.id, format='.h5', transmitted=False).all()

            # Get scan type and add to file list
            for f in list_files:
                f.scan_type = request.form.get(f'select_scan_{f.name_unique}')
            db.session.commit()

            return render_template('upload/check.html')


@bp.route('/upload_scans_xnat', methods=["GET", "POST"])
@login_required
def upload_scans_xnat():
    if request.method == "POST":
        list_files = File.query.filter_by(user_id=current_user.id, format='.h5', transmitted=False).all()

        success = xnat.upload_raw_mr_to_vault(list_files)
        current_app.logger.info(f"Finished upload request to {current_app.config['XNAT_PROJECT_ID_VAULT']}.")

        if success:
            for f in list_files:
                current_app.logger.info(f"Finished upload request of {f.name} to "
                                        f"{f.xnat_subject_id} | {f.xnat_experiment_id} | {f.xnat_scan_id}.")
        else:
            raise AssertionError(f"Something with the xnat upload went wrong.")

        return('Files uploaded to XNAT')


@bp.route('/check', methods=["POST", "GET"])
@login_required
def check():
    return render_template('upload/check.html')


@bp.route('/check_images/<int:timeout>', methods=['GET', 'POST'])
@login_required
def check_images(timeout):

    # Get files which have been transmitted but not yet submitted
    files = File.query.filter_by(user_id=current_user.id, format='.h5', transmitted=True, submitted=False).all()

    current_app.logger.info(f"Number of files {len(files)} transmitted.")

    # Check the status of the container for each scan
    files = xnat.update_container_status(files)
    db.session.commit()

    # Download dicom data for the scans where the container has finished successfully
    files = xnat.download_dcm_images(files)
    db.session.commit()


    # Also include files which have not yet been transmitted to the XNAT server
    files = File.query.filter_by(user_id=current_user.id, format='.h5', submitted=False).all()

    all_recons_performed = True
    if timeout == 0:
        for f in files:
            all_recons_performed *= (f.reconstructed or (f.container_status == 4))
            current_app.logger.info(f'File {f.name} reconstructed? {f.reconstructed} crashed? {f.container_status == 4}'
                                    f'-> all_recons_performed: {all_recons_performed}.')

    # Check for which subjects all files are transmitted and reconstructed
    subject_file_lut = utils.create_subject_file_lookup(files)
    subjects = []
    for subj in subject_file_lut.keys():
        curr_subj_transmitted = True
        curr_subj_reconstructed = True
        for f in subject_file_lut[subj]:
            if f.transmitted == False:
                curr_subj_transmitted = False
            if f.reconstructed == False:
                curr_subj_reconstructed = False
        subjects.append([subj, curr_subj_transmitted, curr_subj_reconstructed])

    current_app.logger.info(f'Timeout {timeout}, all recons performed {all_recons_performed}.')
    current_app.logger.info('We will try to render:')
    for subj in subject_file_lut:
        current_app.logger.info(f'   Subject - {subj}')
        for scan in subject_file_lut[subj]:
            current_app.logger.info(f'      {scan.name}')
    return render_template('upload/check_images.html', subjects=subjects, files_for_subject=subject_file_lut,
                           reload=(all_recons_performed==False))


@bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == "POST":
        if 'cancel' in request.form:
            return redirect(url_for('upload.upload'))
        else:

            # List of files which are not going to be submitted to the Open repo and will be deleted from the Vault
            files_rejected = []

            # First get all files which were not reconstructed
            list_files = File.query.filter_by(user_id=current_user.id, format='.h5', transmitted=True,
                                              reconstructed=False, submitted=False).all()
            files_rejected.extend(list_files)
            current_app.logger.info('Files not reconstructed:')
            for f in list_files:
                current_app.logger.info(f'   {f.name}')

            # Now get files which were reconstructed but shall not be submitted
            list_files = File.query.filter_by(user_id=current_user.id, format='.h5', transmitted=True,
                                              reconstructed=True, submitted=False).all()

            current_app.logger.info('Files reconstructed:')
            for f in list_files:
                current_app.logger.info(f'   {f.name}')

            for f in list_files:
                if 'check_'+str(f.subject) not in request.form:
                    files_rejected.append(f)

            xnat.delete_scans_from_vault(files_rejected)
            current_app.logger.info('Files rejected:')
            for f in files_rejected:
                db.session.delete(f)
                current_app.logger.info(f'   {f.name}')

            db.session.commit()

            # Finally get files which were reconstructed and should be submitted to the Open repo
            list_files = File.query.filter_by(user_id=current_user.id, format='.h5', transmitted=True,
                                              reconstructed=True, submitted=False).all()
            files_submitted = []
            current_app.logger.info('Files to be submitted to open project:')
            for f in list_files:
                if 'check_'+ str(f.subject) in request.form:
                    files_submitted.append(f)
                    current_app.logger.info(f'   {f.name}')

            # Add snapshots
            xnat.add_snapshot_images(files_submitted)

            # Commit subjects to open project
            xnat.commit_subjects_to_open(files_submitted)

            for f in files_submitted:
                f.submitted = True

            db.session.commit()

            subject_file_lut = utils.create_subject_file_lookup(files_submitted)

        return render_template('home/thank_you.html', submitted_subjects=list(subject_file_lut.keys()),
                               files_for_submitted_subject=subject_file_lut)
