import numpy as np
import sys, os

from collections import Counter
import sirf.Gadgetron as pMR
from sirf.Utilities import assert_validity

from pathlib import Path, PosixPath

def main(path_in, path_out):

    print(f"Reading from {path_in}, writing into {path_out}")
    assert os.access(path_in, os.R_OK), f"You don't have write permission in {path_in}"
    assert os.access(path_out, os.W_OK), f"You don't have write permission in {path_out}"

    list_of_files = sorted(path_in.glob("*.h5"))

    for mrfile in list_of_files:

        cpath_out = path_out / f"recon_{mrfile.stem}"
        sirf_recon(mrfile, cpath_out)

    print('python finished')
    return 0

def sirf_recon(fname_in, path_out):
    
    assert isinstance(fname_in, PosixPath),f'Expecting object of type {PosixPath}, got {type(fname_in)}'
    assert isinstance(path_out, PosixPath),f'Expecting object of type {PosixPath}, got {type(path_out)}'

    path_out.mkdir(parents=True, exist_ok=False)

    print(f"Starting reconstruction for {fname_in}")

    image_data = reconstruct_data(fname_in)
    dcm_output_name = path_out / fname_in.with_suffix('.dcm').name
    
    image_data.write(str(dcm_output_name))

def reconstruct_data(fname_in):
    
    rawdata = prep_rawdata(fname_in)

    recon = setup_recon()
    recon.set_input(rawdata)
    recon.process()

    image_data = recon.get_output('image PhysioInterp')
    image_data = normalise_image_data(image_data)
    return image_data

def prep_rawdata(fname_in):

    rawdata = pMR.AcquisitionData(str(fname_in))
    rawdata = exclude_undersampled_phases(rawdata)
    rawdata = pMR.preprocess_acquisition_data(rawdata)
    rawdata.sort()

def exclude_undersampled_phases(rawdata):
    cardiac_phase = rawdata.get_info('phase')
    cpc = Counter(cardiac_phase)
    pe_pts_per_phase = [cpc[key] for key in cpc ]
    median_num_ro_per_phase = np.median(sorted(pe_pts_per_phase))
    undersampled_phases = np.where(pe_pts_per_phase < median_num_ro_per_phase)

    fullysampled_idx = np.where(np.invert(np.isin(cardiac_phase, undersampled_phases)))
    rawdata = rawdata.get_subset(fullysampled_idx)

    return rawdata

def setup_recon():

    recon_gadgets = ['AcquisitionAccumulateTriggerGadget(trigger_dimension=repetition)',
            'BucketToBufferGadget(split_slices=true, verbose=false)',
            'GenericReconCartesianReferencePrepGadget',
            'GenericReconCartesianGrappaGadget(send_out_gfactor=false)',
            'GenericReconFieldOfViewAdjustmentGadget',
            'GenericReconImageArrayScalingGadget',
            'ImageArraySplitGadget',
            'PhysioInterpolationGadget(phases=30, mode=0, first_beat_on_trigger=true, interp_method=BSpline)'
            ]

    recon = pMR.Reconstructor(recon_gadgets)

    return recon

def normalise_image_data(img):

    assert_validity(img, pMR.ImageData)

    img = img.abs()

    img_max = np.max(img.as_array())
    img_min = np.min(img.as_array())

    img = 2**16 * (img - img_min)/(img_max-img_min)

    return img

### looped reconstruction over files in input path
path_in  = Path(sys.argv[1])
path_out = Path(sys.argv[2])

main(path_in, path_out)