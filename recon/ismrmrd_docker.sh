#!/bin/bash
fpath_siemens=$1
fname_siemens=$2

stem_siemens=${fname_siemens%%.dat}
fname_ismrmrd="${stem_siemens}.h5"

measurement="1"
container_id=$(docker run -d -it -v $fpath_siemens:/tmp s2i)

docker exec -it $container_id /bin/bash -c "source ~/.bashrc && siemens_to_ismrmrd -z $measurement -f /tmp/${fname_siemens} -o /tmp/${fname_ismrmrd}"

docker rm -f $container_id