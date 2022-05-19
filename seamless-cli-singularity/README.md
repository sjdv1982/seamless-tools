Howto
=====

- Define the Seamless-minimal Singularity container file as an environmental variable, e.g:
export SEAMLESS_MINIMAL_SINGULARITY_IMAGE=seamless-minimal.sif

- build the Seamless-minimal Singularity container from the Docker image:
singularity build --fakeroot $SEAMLESS_MINIMAL_SINGULARITY_IMAGE docker://rpbs/seamless-minimal:0.8

- You can then use the commands in this folder as drop-in replacements for the seamless-cli commands, without installing Docker.