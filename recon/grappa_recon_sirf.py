'''
Author: Johannes Mayer
'''
import argparse
from pathlib import Path

# import engine module
from sirf.Gadgetron import AcquisitionData, preprocess_acquisition_data, CartesianGRAPPAReconstructor

# # process command-line options
# data_file = args['--file']
# data_path = args['--path']

# output_file = args['--output']

parser = argparse.ArgumentParser(description="Run SIRF GRAPPA reconstruction.")
parser.add_argument('-i', '--input', help='filename of ISMRMRD file with .h5 suffix used as input.')
parser.add_argument('-o', '--output', help='filename of Dicom file used as output with .dcm suffix.')

args = parser.parse_args()
print(args.input)
print(args.output)


def main():
    
    # locate the input data file and check it is a valid input.
    input_file = Path(args.input)
    
    if not input_file.is_file():
        raise FileNotFoundError(f"The file {input_file} could not be found.")
    
    assert input_file.suffix == '.h5', f"The file extension should be .h5, you supplied {input_file.suffix}"
    
    # Create an acquisition container of type AcquisitionData
    print('---\n reading in file %s...' % input_file)
    acq_data = AcquisitionData(str(input_file))
    
    # Pre-process this input data.
    # (Currently this is a Python script that just sets up a 3 chain gadget.
    # In the future it will be independent of the MR recon engine.)
    print('---\n pre-processing acquisition data...')
    preprocessed_data = preprocess_acquisition_data(acq_data)
    
    # Perform reconstruction of the preprocessed data.
    # 1. set the reconstruction to be for Cartesian GRAPPA data.
    recon = CartesianGRAPPAReconstructor()
    
    # 2. set the reconstruction input to be the data we just preprocessed.
    recon.set_input(preprocessed_data)
    
    # 3. run (i.e. 'process') the reconstruction.
    print('---\n reconstructing...\n')
    recon.process()

    # retrieve reconstruced image and G-factor data
    image_data = recon.get_output('image')
    
    if args.output is not None:
      # write images to a new group in args.output
      # named after the current date and time
      print(f'writing to {args.output}')
      image_data.write(args.output)

try:
    main()
    print('\n=== done with %s' % __file__)

except Exception as e:
    # display error information
    print(e)
    exit(1)
