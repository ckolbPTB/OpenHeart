#!/bin/bash
fpath_data=$1
#image_name="johannesmayer/sirf_qc"
image_name="ckolbptb/sirf_qc"
container_id=$(docker run -d -it -v $fpath_data:/tmp ${image_name})


fname_reconscript="mr_cine_recon.py"
fname_dcm_dummy="dummyfile.dcm"

docker cp ./$fname_reconscript $container_id:/tmp

docker exec -it $container_id /bin/bash -c "source ~/.bashrc && gadgetron & source ~/.bashrc && python3 /tmp/${fname_reconscript} /tmp /tmp"

rm ${fpath_data}/${fname_dcm_dummy}
rm ${fpath_data}/${fname_reconscript}

docker rm -f $container_id
