#!/bin/bash

container_id=$(docker run -d -it -v /media/sf_CCPPETMR/XNAT/xnat_example_data/Subject1/:/tmp ckolbptb/sirf_qc)


fname_reconscript="mr_cine_recon.py"
docker cp ./$fname_reconscript $container_id:/tmp
docker exec -it $container_id /bin/bash -c "source ~/.bashrc && gadgetron & source ~/.bashrc && python3 /tmp/${fname_reconscript} /tmp /tmp"

docker rm -f $container_id