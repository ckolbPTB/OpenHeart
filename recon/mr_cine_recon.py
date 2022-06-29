import numpy as np
import nibabel as nib
import sys, re, os
import glob

from collections import Counter
import sirf.Gadgetron as pMR
from sirf.Utilities import assert_validity

def write_nii(fname, img):
    print(f"writing {fname}")
    data = np.abs(np.squeeze(img.as_array()))
    nii = nib.Nifti1Image(data, np.eye(4))
    nib.save(nii, fname)

def exclude_undersampled_phases(rawdata):
    cardiac_phase = rawdata.get_info('phase')
    cpc = Counter(cardiac_phase)
    pe_pts_per_phase = [cpc[key] for key in cpc ]
    median_num_ro_per_phase = np.median(sorted(pe_pts_per_phase))
    undersampled_phases = np.where(pe_pts_per_phase < median_num_ro_per_phase)

    fullysampled_idx = np.where(np.invert(np.isin(cardiac_phase, undersampled_phases)))
    rawdata = rawdata.get_subset(fullysampled_idx)

    return rawdata
    

path_in = sys.argv[1]
path_out = sys.argv[2]

print(path_in)
print(os.stat(path_in).st_uid)
print(os.access(path_in, os.R_OK))
print(os.access(path_in, os.W_OK))

print(path_out)
print(os.stat(path_out).st_uid)
print(os.access(path_out, os.R_OK))
print(os.access(path_out, os.W_OK))

list_of_files = []

for file in os.listdir(path_in):
        list_of_files.append(os.path.join(path_in,file))
for name in list_of_files:
    print('in ', name)
    
# Get all h5 files
data = [os.path.basename(x) for x in glob.glob(path_in + '/*.h5')]

for name in data:
    print('h5 ', name)
    
file_in = data[0]

print('python started again')

rawdata = pMR.AcquisitionData(path_in + '/' + file_in)
rawdata = exclude_undersampled_phases(rawdata)

rawdata = pMR.preprocess_acquisition_data(rawdata)
rawdata.sort()

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
recon.set_input(rawdata)
recon.process()

image_data = recon.get_output('image PhysioInterp')
print('Size of image data with PhysioInterpolationGadget: ', image_data.dimensions())

write_nii(path_out + '/' + file_in.replace('.h5','.nii'), image_data)

image_data = image_data.abs()
img_values = image_data.as_array()
img_values = (img_values - np.min(img_values))/ (np.max(img_values) - np.min(img_values))
image_data = image_data.fill(img_values)

image_data *= 2^32
file_out = file_in.replace('.h5', '.dcm')
image_data.write(path_out + '/' + file_out)

print('python finished')
