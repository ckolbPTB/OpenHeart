from pathlib import Path
import pydicom
import imageio
import glob, os
import numpy as np
import matplotlib.pyplot as plt
import hashlib
import docker

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


def preprocess_dicoms_for_gif(dicom_path: Path):

    dcm_files = sorted(dicom_path.glob("*.dcm"))

    num_files = len(dcm_files)
    current_app.logger.info(f"Currently we found {num_files} dicoms.")

    # Get header information for sorting
    sort_key_words = ['SliceLocation', 'EchoTime']
    sort_idx = np.zeros((len(sort_key_words), num_files), dtype=np.float32)
    for ind, f in enumerate(dcm_files):
        ds = pydicom.dcmread(str(f))
        for jnd in range(len(sort_key_words)):
            if sort_key_words[jnd] in ds:
                sort_idx[jnd, ind] = float(ds.data_element(sort_key_words[0]).value)
    slice_idx = np.lexsort(sort_idx)

    # ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRBigEndian
    # Read data
    ds = [pydicom.dcmread(str(f)) for f in dcm_files]

    print('FIX FOR BROKEN DICOM!!!!!')
    for d in ds:
        d.BitsAllocated = 16
        d.SamplesPerPixel = 1
        d.PhotometricInterpretation = 'MONOCHROME1'
        d.PixelRepresentation = 1
        d.BitsStored = 16

    ds[:] = map(lambda x: x.pixel_array, ds)

    # Transform to array and resort
    ds = np.asarray(ds)
    ds = ds[slice_idx,...]
    ds = np.moveaxis(ds, 0, -1)
    ds = np.reshape(ds, ds.shape[:2] + (-1,))

    return ds, num_files

def create_qc_gif(dicom_path: Path, filename_output_with_ext:Path):

    ds, num_files = preprocess_dicoms_for_gif(dicom_path)
    fps = 30
    gif_dur_seconds = num_files / fps
    save_gif(ds, filename_output_with_ext, cmap='gray', min_max_val=[], total_dur=gif_dur_seconds)

    return None

def save_gif(im, fpath_output_with_ext:Path, cmap='gray', min_max_val=[], total_dur=2):

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
    imageio.mimsave(str(fpath_output_with_ext) , anim_im, duration=dur)

    return None

def create_md5_from_string(some_string):
    return hashlib.md5(some_string.encode('utf-8')).hexdigest()

def create_md5_from_file(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
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

def rename_h5_file(fname_out):

    md5_hash = create_md5_from_file(str(fname_out))
    cfile_name = (fname_out.parent / md5_hash).with_suffix(".h5")
    try:
        current_app.logger.info(f"Trying to rename {fname_out} into {cfile_name}.")
        fname_out.rename(cfile_name)
    except FileExistsError:
        current_app.logger.warning(f"You tried to rename {fname_out} into {cfile_name}, but the latter alraedy exists. Ignoring request.")

    return cfile_name

def clean_up_user_files():

    if current_user.is_authenticated:
        list_user_files = File.query.filter_by(user_id=current_user.id,
                                            submitted=False).all()

        for f in list_user_files:
            if os.path.isfile(f.name):
                os.remove(f.name)
            if os.path.isfile(f.name_unique):
                os.remove(f.name_unique)
            db.session.delete(f)

        db.session.commit()

    return(True)

def create_subject_file_lookup(list_files):

    list_subjects = set([f.subject for f in list_files])

    sub_id_lut = {}
    for sub in list_subjects:
        sub_id_lut[sub] = []

    for f in list_files:
        sub_id_lut[f.subject].append(f)

    return sub_id_lut
