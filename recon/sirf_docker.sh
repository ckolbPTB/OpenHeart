#!/bin/bash
fpath_data=$1
image_name="johannesmayer/sirf_qc"

container_id=$(docker run -d -it --rm --name=sirf-qc --net=host -v $fpath_data:/tmp ${image_name})

fname_reconscript="mr_cine_recon.py"

docker cp ./$fname_reconscript $container_id:/tmp

docker exec -it $container_id /bin/bash -c "source ~/.bashrc && python3 /tmp/${fname_reconscript} /tmp /tmp"

rm ${fpath_data}/${fname_reconscript}

docker stop sirf-qc
