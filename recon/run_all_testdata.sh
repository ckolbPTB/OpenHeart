#!/bin/bash

root_path="/media/sf_CCPPETMR"
fpath_td="${root_path}/XNAT/xnat_example_data"

# Declare an array of string with type
declare -a subj1=("meas_MID39_cine" "meas_MID40_cine" "meas_MID47_cine" )
# declare -a subj2=("meas_MID34_cine" "meas_MID36_cine" "meas_MID37_cine" "meas_MID43_cine")
declare -a subj2=("meas_MID34_cine" "meas_MID36_cine" "meas_MID37_cine" "meas_MID43_cine")
declare -a subj3=("meas_MID47_cine")

# Iterate the string array using for loop
# for val in ${subj1[@]}; do
   
#    input="${fpath_td}/Subject1/${val}.h5"
#    output="${root_path}/gt_recon_subj1_${val}"

#    bash gt_grappa.sh ${input} ${output}
# done

for val in ${subj2[@]}; do
   
   input="${fpath_td}/Subject2/${val}.h5"
   output="${root_path}/gt_recon_subj2_${val}"

   bash gt_grappa.sh ${input} ${output}
done

for val in ${subj3[@]}; do
   
   input="${fpath_td}/Subject3/${val}.h5"
   output="${root_path}/gt_recon_subj3_${val}"

   bash gt_grappa.sh ${input} ${output}
done