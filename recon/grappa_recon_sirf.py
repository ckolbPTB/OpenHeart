'''
Author: Johannes Mayer, Evgueni Ovtchinnikov
'''
import argparse
from pathlib import Path
import nibabel as nib
import numpy as np
from sirf.Gadgetron import AcquisitionData, preprocess_acquisition_data, CartesianGRAPPAReconstructor, Gadget, Reconstructor, FullySampledReconstructor

from collections import Counter

parser = argparse.ArgumentParser(description="Run SIRF GRAPPA reconstruction.")
parser.add_argument('-i', '--input', help='filename of ISMRMRD file with .h5 suffix used as input.')
parser.add_argument('-o', '--output', help='filename of Dicom file used as output with .dcm suffix.')



args = parser.parse_args()
fname_nii = Path(args.output).with_suffix(".nii")

print(f"Running SIRF Generic GRAPPA recon of {args.input}, storing it to {args.output}, with {fname_nii} as a reference image.")

def write_nii(fname, sirf_img):

    data = np.abs(sirf_img.as_array())
    nii = nib.Nifti1Image(data, np.eye(4))
    nib.save(nii, str(fname))

def main():
    
    # locate the input data file and check it is a valid input.
    input_file = Path(args.input)
    
    if not input_file.is_file():
        raise FileNotFoundError(f"The file {input_file} could not be found.")
    
    assert input_file.suffix == '.h5', f"The file extension should be .h5, you supplied {input_file.suffix}"
    
    # Create an acquisition container of type AcquisitionData
    print('---\n reading in file %s...' % input_file)
    acq_data = AcquisitionData(str(input_file))
    
    # Check the data consistency
    phases = sorted(list(acq_data.get_info("phase")))
    phasecount = Counter(phases)
    print(phasecount)
    
    # Pre-process this input data.
    # (Currently this is a Python script that just sets up a 3 chain gadget.
    # In the future it will be independent of the MR recon engine.)
    print('---\n pre-processing acquisition data...')
    preprocessed_data = preprocess_acquisition_data(acq_data)
    
    # Perform reconstruction of the preprocessed data.
    # 1. set the reconstruction to be for Cartesian GRAPPA data.
    recon = FullySampledReconstructor()
    recon.set_input(preprocessed_data)
    recon.process()
    image_data = recon.get_output('image')
    
    image_data = image_data.abs()
    image_data.write(args.output)

    recon = CartesianGRAPPAReconstructor()
    recon.set_input(preprocessed_data)
    recon.process()
    
    image_data = recon.get_output('image')
    image_data = image_data.abs()
    image_data.write(args.output)
        
try:
    main()
    print('\n=== done with %s' % __file__)

except Exception as e:
    # display error information
    print(e)
    exit(1)

# CALCULATE G-FACTOR MAP
# recon_gadgets = ['AcquisitionAccumulateTriggerGadget',
#         'BucketToBufferGadget', 
#         'GenericReconCartesianReferencePrepGadget', 
#         'GRAPPA:GenericReconCartesianGrappaGadget', 
#         'GenericReconFieldOfViewAdjustmentGadget', 
#         'GenericReconImageArrayScalingGadget', 
#         'ImageArraySplitGadget',
#         'PhysioInterpolationGadget(phases=30, mode=0, first_beat_on_trigger=true, interp_method=BSpline)'
#         ]
# recon = Reconstructor(recon_gadgets)

# image_data = recon.get_output('Image PhysioInterp')
