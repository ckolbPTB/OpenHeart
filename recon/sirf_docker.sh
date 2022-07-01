#!/bin/bash
fpath_data="/media/sf_CCPPETMR/XNAT/xnat_example_data/Subject1/"
container_id=$(docker run -d -it -v $fpath_data:/tmp ckolbptb/sirf_qc)
# container_id=$(docker run -d -it -v /media/sf_CCPPETMR/XNAT/Temp/:/tmp ckolbptb/sirf_qc)


fname_reconscript="mr_cine_recon.py"
fname_dcm_dummy="dummyfile.dcm"

docker cp ./$fname_reconscript $container_id:/tmp
docker cp ./$fname_dcm_dummy $container_id:/tmp

docker exec -it $container_id /bin/bash -c "source ~/.bashrc && gadgetron & source ~/.bashrc && python3 /tmp/${fname_reconscript} /tmp /tmp"

rm ${fpath_data}/${fname_dcm_dummy}
rm ${fpath_data}/${fname_reconscript}

docker rm -f $container_id