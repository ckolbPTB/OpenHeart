#!/bin/bash

echo "Running GRAPPA reconstruction using Gadgetron."

fname_in=$1
fdir_out=$2
fname_config="./gtpipelines/Generic_Cartesian_Grappa.xml"
# fname_config="./gtpipelines/dicom.xml"

echo "Input file is ${fname_in} and output directory is ${fdir_out}"
echo "Stream configuration is ${fname_config}}"

# detemining place of reconstruction and performing it
dir_of_recon=$(pwd)
gadgetron_ismrmrd_client --filename=$fname_in --outfile=" " --config-local=$fname_config

# deleting junk files
find -type f -name "*_attrib.xml" -delete 

#  
python3 gtpipelines/postprocess_dcm.py -i=$dir_of_recon -o=${fdir_out}
