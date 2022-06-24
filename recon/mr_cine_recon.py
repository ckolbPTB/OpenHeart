import numpy as np
import nibabel as nib
import sys, re, os
import glob

import sirf.Gadgetron as pMR
from sirf.Utilities import assert_validity

def coilmaps_from_rawdata(ad):

	assert_validity(ad, pMR.AcquisitionData)

	csm = pMR.CoilSensitivityData()
	csm.smoothness = 50
	csm.calculate(ad)

	return csm

class EncOp:

    def __init__(self,am):
        assert_validity(am, pMR.AcquisitionModel)
        self._am = am

    def __call__(self,x):
        assert_validity(x, pMR.ImageData)
        return self._am.backward(self._am.forward(x))

def conjGrad(A,x,b,tol=0,N=10):

    r = b - A(x)
    p = r.copy()
    for i in range(N):
        Ap = A(p)
        alpha = np.vdot(p.as_array()[:],r.as_array()[:])/np.vdot(p.as_array()[:],Ap.as_array()[:])
        x = x + alpha*p
        r = b - A(x)
        if np.sqrt( np.vdot(r.as_array(), r.as_array()) ) < tol:
            print('Itr:', i)
            break
        else:
            beta = -np.vdot(r.as_array()[:],Ap.as_array()[:])/np.vdot(p.as_array()[:],Ap.as_array()[:])
            p = r + beta*p
    return x 

def iterative_reconstruct_data(ad, csm=None, num_iter=5):
	
	assert_validity(ad, pMR.AcquisitionData)
	if csm is not None:
		assert_validity(csm, pMR.CoilSensitivityData)
	else:
		csm = coilmaps_from_rawdata(ad)
	
	img = pMR.ImageData()
	img.from_acquisition_data(ad)

	am = pMR.AcquisitionModel(ad, img)
	am.set_coil_sensitivity_maps(csm)
	E = EncOp(am)
	x0 = am.backward(ad)
	return conjGrad(E,x0,x0, tol=0, N=num_iter)




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

print(f"the maximum number of readout points is {np.max(rawdata.get_info('number_of_samples'))}")

rawdata = pMR.preprocess_acquisition_data(rawdata)
rawdata.sort()

recon = pMR.CartesianGRAPPAReconstructor()
# recon = pMR.FullySampledReconstructor()
recon.set_input(rawdata)
recon.process()
img_data = recon.get_output()

# img_data = iterative_reconstruct_data(rawdata)


img_data = img_data.abs()
img_values = img_data.as_array()
img_values = (img_values - np.min(img_values))/ (np.max(img_values) - np.min(img_values))
img_data = img_data.fill(img_values)

img_data *= 2^32
file_out = file_in.replace('.h5', '.dcm')
img_data.write(path_out + '/' + file_out)

#file_out = file_in.replace('.h5', '.nii')
#img_data.write(path_out + '/' + file_out)

#nii_img = pReg.NiftiImageData(img_data)
#file_out = file_in.replace('.h5', '_reg.nii')
#nii_img.write(path_out + '/' + file_out)



print('python finished')


# #%% CALCULATE G-FACTOR MAP
# recon_gadgets = ['AcquisitionAccumulateTriggerGadget',
#         'BucketToBufferGadget', 
#         'GenericReconCartesianReferencePrepGadget', 
#         'GRAPPA:GenericReconCartesianGrappaGadget', 
#         'GenericReconFieldOfViewAdjustmentGadget', 
#         'GenericReconImageArrayScalingGadget', 
#         'ImageArraySplitGadget',
#         'PhysioInterpolationGadget(phases=30, mode=0, first_beat_on_trigger=true, interp_method=BSpline)'
#         ]
        
# recon = pMR.Reconstructor(recon_gadgets)
# recon.set_gadget_property('GRAPPA', 'send_out_gfactor', True)
# recon.set_input(rawdata)
# recon.process()
