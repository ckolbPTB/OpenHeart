from pathlib import Path
import pydicom
import imageio
import glob, os, shutil
import numpy as np
import matplotlib.pyplot as plt
import hashlib
import docker
import skimage

from flask import current_app
from flask_login import current_user

from openheart.database import db, File

def ismrmrd_2_xnat(ismrmrd_header):
    xnat_dict = {}

    xnat_dict['scans'] = 'xnat:mrScanData'
    xnat_dict['xnat:mrScanData/fieldStrength'] = str(ismrmrd_header.acquisitionSystemInformation.systemFieldStrength_T) + 'T'

    xnat_dict['xnat:mrScanData/parameters/subjectPosition'] = ismrmrd_header.measurementInformation.patientPosition.value

    xnat_dict['xnat:mrScanData/parameters/voxelRes.units'] = 'mm'
    xnat_dict['xnat:mrScanData/parameters/voxelRes/x'] = float(ismrmrd_header.encoding[0].reconSpace.fieldOfView_mm.x / float(ismrmrd_header.encoding[0].reconSpace.matrixSize.x))
    xnat_dict['xnat:mrScanData/parameters/voxelRes/y'] = float(ismrmrd_header.encoding[0].reconSpace.fieldOfView_mm.y / float(ismrmrd_header.encoding[0].reconSpace.matrixSize.y))
    xnat_dict['xnat:mrScanData/parameters/voxelRes/z'] = float(ismrmrd_header.encoding[0].reconSpace.fieldOfView_mm.z / float(ismrmrd_header.encoding[0].reconSpace.matrixSize.z))

    xnat_dict['xnat:mrScanData/parameters/fov/x'] = int(ismrmrd_header.encoding[0].reconSpace.fieldOfView_mm.x)
    xnat_dict['xnat:mrScanData/parameters/fov/y'] = int(ismrmrd_header.encoding[0].reconSpace.fieldOfView_mm.y)

    xnat_dict['xnat:mrScanData/parameters/matrix/x'] = int(ismrmrd_header.encoding[0].reconSpace.matrixSize.x)
    xnat_dict['xnat:mrScanData/parameters/matrix/y'] = int(ismrmrd_header.encoding[0].reconSpace.matrixSize.y)

    xnat_dict['xnat:mrScanData/parameters/partitions'] = int(ismrmrd_header.encoding[0].encodingLimits.kspace_encoding_step_2.maximum - ismrmrd_header.encoding[0].encodingLimits.kspace_encoding_step_2.minimum + 1)
    xnat_dict['xnat:mrScanData/parameters/tr'] = float(ismrmrd_header.sequenceParameters.TR[0])
    xnat_dict['xnat:mrScanData/parameters/te'] = float(ismrmrd_header.sequenceParameters.TE[0])
    xnat_dict['xnat:mrScanData/parameters/ti'] = float(ismrmrd_header.sequenceParameters.TI[0])
    xnat_dict['xnat:mrScanData/parameters/flip'] = int(ismrmrd_header.sequenceParameters.flipAngle_deg[0])
    xnat_dict['xnat:mrScanData/parameters/sequence'] = ismrmrd_header.sequenceParameters.sequence_type

    xnat_dict['xnat:mrScanData/parameters/echoSpacing'] = float(ismrmrd_header.sequenceParameters.echo_spacing[0])

    return(xnat_dict)


def max99perc(dat):
    dat = np.sort(dat.flatten())
    return (dat[int(np.round(dat.shape[0] * 0.99))])


def min01perc(dat):
    dat = np.sort(dat.flatten())
    return (dat[int(np.round(dat.shape[0] * 0.01))])


def read_and_process_dicoms(dicom_path:Path):
    '''
    Reads all dicoms in a folder and processes them into an array that can be stored as a gif.
    Data are sorted wrt. to their SliceLocation and EchoTime fields in the dicom tags.
    input:
        dicom_path: pathlib.Path object for the folder containing the dicoms
    output:
        ds: numpy array containing the image data
        num_files: number of detected dicoms
    '''
    dcm_files = sorted(dicom_path.glob("*.dcm"))

    num_files = len(dcm_files)
    current_app.logger.info(f"Currently we found {num_files} dicoms.")

    # Get header information for sorting
    sort_key_words = ['ImageNumber', 'EchoTime', 'SliceLocation']
    sort_idx = np.zeros((len(sort_key_words), num_files), dtype=np.float32)
    for ind, f in enumerate(dcm_files):
        ds = pydicom.dcmread(str(f))
        for jnd in range(len(sort_key_words)):
            if sort_key_words[jnd] in ds:
                sort_idx[jnd, ind] = float(ds.data_element(sort_key_words[jnd]).value)
    slice_idx = np.lexsort(sort_idx)

    # Read data
    ds = [pydicom.dcmread(str(f)) for f in dcm_files]
    ds[:] = map(lambda x: x.pixel_array, ds)

    # Transform to array and resort
    ds = np.asarray(ds)
    ds = ds[slice_idx,...]
    ds = np.moveaxis(ds, 0, -1)
    ds = np.reshape(ds, ds.shape[:2] + (-1,))

    # Number of slices
    slice_idx = sort_key_words.index('SliceLocation')
    num_slices = len(np.unique(sort_idx[slice_idx,:]))

    # Split into slices
    ds_slices = np.array_split(ds, num_slices, axis=2)

    # Montage for overview
    for dyn in range(ds_slices[0].shape[2]):
        tmp = skimage.util.montage([x[:,:,dyn] for x in ds_slices], fill=0)
        if dyn == 0:
            ds_montage = np.zeros(tmp.shape + (ds_slices[0].shape[2],))
        ds_montage[:,:,dyn] = tmp

    return ds, ds_slices[int(num_slices//2)], ds_montage, num_files


def get_dicom_header(dicom_path:Path):
    '''
    Get dicom header information from folder with dicom files in it.
    input:
        dicom_path: pathlib.Path object where dicoms are located.
    output:
        dicom headers of all files
    '''
    assert dicom_path.exists(), f"The directory where the dicoms should be found does not exist."

    dcm_files = sorted(dicom_path.glob("*.dcm"))
    dcm_header = []
    for ind, f in enumerate(dcm_files):
        dcm_header.append(pydicom.dcmread(str(f), stop_before_pixels=True))
    return(dcm_header)


def create_qc_gif(dicom_path:Path, filename_output_with_ext:Path):
    '''
    Stores a gif generated from dicoms found in dicom_path into the file filename_output_with_ext.
    Parent path of filename_output_with_ext has to exist.
    gif speed is set to 30 fps.
    input:
        dicom_path: pathlib.Path object where dicoms are located.
        filename_output_with_ext: pathlib.Path object where gif should be stored including .gif extension.
    output:
        None
    '''
    assert dicom_path.exists(), f"The directory where the dicoms should be found does not exist."
    assert filename_output_with_ext.parent.exists(), f"The directory {filename_output_with_ext.parent} into which the .gif should be stored does not exist."

    ds, ds_central_slice, ds_montage, num_files = read_and_process_dicoms(dicom_path)

    fps = 30
    gif_dur_seconds = num_files / fps

    # Gif for QC on homepage
    save_gif(ds, str(filename_output_with_ext), cmap='gray', min_max_val=[], total_dur=gif_dur_seconds)

    # Gifs for xnat preview (snapshots)
    save_gif(ds_central_slice, str(filename_output_with_ext).replace('.gif', '_snapshot_t.gif'),
             cmap='gray', min_max_val=[], total_dur=1)
    save_gif(ds_montage, str(filename_output_with_ext).replace('.gif', '_snapshot.gif'), cmap='gray',
             min_max_val=[], total_dur=1)

    return None


def save_gif(im:np.array, fpath_output_with_ext:str, cmap='gray', min_max_val=[], total_dur=2.0):
    '''
    Function to store a numpy array into a .gif file of duration total_dur.
    '''
    # Translate image from grayscale to rgb
    cmap = plt.get_cmap(cmap)
    if len(min_max_val) == 0:
        im = (im - min01perc(im)) / (max99perc(im) - min01perc(im))
    else:
        im = (im - min_max_val[0]) / (min_max_val[1] - min_max_val[0])
    im = cmap(im)
    im_rgb = (im * 255).astype(np.uint8)[:,:,:,:3]

    # Check for 2D images
    if len(im_rgb.shape) == 3:
        im_rgb = im_rgb[:,:,np.newaxis,:]

    anim_im = []
    dur = []
    for tnd in range(im_rgb.shape[2]):
        anim_im.append(im_rgb[:, :, tnd, :])
        dur.append(total_dur/im_rgb.shape[2])
    imageio.mimsave(fpath_output_with_ext , anim_im, duration=dur)

    return None


def create_md5_from_string(some_string):
    return hashlib.md5(some_string.encode('utf-8')).hexdigest()


def create_md5_from_file(filepath_with_ext:str):
    '''
    Function generating md5 hash from file content, identifiying files uniquely.
    '''
    hash_md5 = hashlib.md5()
    with open(filepath_with_ext, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def valid_extension(zipfile_content):
    list_valid_suffixes = ['.h5', '.dat']
    return zipfile_content.suffix in list_valid_suffixes 


def convert_dat_file(filename, measurement_number=1):
    filename = Path(filename)
    filepath = filename.parent
    volumes = [f"{filepath}:/input", f"{filepath}:/output"] 

    filename_output = filename.with_suffix('.h5')
    assert not filename_output.is_file(), f"You try to convert {filename} but {filename_output} already exists.\
        Conversion would lead to appending to the output file. Aborting."

    conversion_command = f"siemens_to_ismrmrd -z {measurement_number} -f /input/{filename.name} -o /output/{filename_output.name}"

    client = docker.from_env()
    client.containers.run(image="johannesmayer/s2i", command=conversion_command, volumes=volumes, detach=False)
    return filename_output


def rename_h5_file(fname_file_with_ext:Path):
    '''
    Renames a file into a unique filename based on an mh5 hash from its file content
    '''
    md5_hash = create_md5_from_file(str(fname_file_with_ext))
    cfile_name = (fname_file_with_ext.parent / md5_hash).with_suffix(".h5")
    try:
        current_app.logger.info(f"Trying to rename {fname_file_with_ext} into {cfile_name}.")
        fname_file_with_ext.rename(cfile_name)
    except FileExistsError:
        current_app.logger.warning(f"You tried to rename {fname_file_with_ext} into {cfile_name}, but the latter alraedy exists. Ignoring request.")

    return cfile_name


def clean_up_user_files(recreate_user_folders=False):
    '''
    Function removing unique folders of the current user with its content.
    The folder names are 'Uid'+str(current_user.id) and one is located in
    OH_DATA_PATH -> uploaded zip files, extracted raw files, downloaded
                    dicom files,...
    and one in
    OH_APP_PATH + '/src/openheart/static/ -> animated gifs

    If recreate_user_folders == True then the two folders are created again
    as empty folders.
    '''
    if current_user.is_authenticated:
        user_folder = 'Uid' + str(current_user.id)
        oh_data_path_user = Path(current_app.config['DATA_FOLDER'] + user_folder)
        oh_app_path_user = Path(current_app.config['OH_APP_PATH'] + '/src/openheart/static/' + user_folder)

        # Remove animated gifs
        if Path.exists(oh_app_path_user):
            shutil.rmtree(oh_app_path_user)

        if Path.exists(oh_data_path_user):
            # Remove any files in oh_data_path_user from the database
            for f in oh_data_path_user.iterdir():
                # Check both for original files and unique file names
                user_file = File.query.filter_by(user_id=current_user.id, submitted=False, name_unique=str(f)).all()
                for uf in user_file:
                    db.session.delete(uf)

                user_file = File.query.filter_by(user_id=current_user.id, submitted=False, name=str(f)).all()
                for uf in user_file:
                    db.session.delete(uf)

            db.session.commit()

            # Remove uploaded zip files, extracted raw files, downloaded dicom files,...
            shutil.rmtree(oh_data_path_user)

        # Create empty folders for user
        if recreate_user_folders:
            oh_data_path_user.mkdir()
            oh_app_path_user.mkdir()

    return(True)

def create_subject_file_lookup(list_files):

    list_subjects = set([f.subject for f in list_files])

    sub_id_lut = {}
    for sub in list_subjects:
        sub_id_lut[sub] = []

    for f in list_files:
        sub_id_lut[f.subject].append(f)

    return sub_id_lut
