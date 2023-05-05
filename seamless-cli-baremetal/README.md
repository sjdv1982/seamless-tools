Howto
=====

- Install mamba in your conda base image:
`conda install mamba -n base -c conda-forge`

- build the seamless-baremetal conda environment:
 `mamba env create --force --file seamless-cli-baremetal/environment.yml`

- Optional: You can use the Git version of Seamless instead of the installed version. This is useful if you want to do Seamless development.
First, conda activate seamless-baremetal or another conda environment cloned from it. Then:

```bash
git clone https://github.com/sjdv1982/seamless.git /home/user/seamless
mamba install -c conda-forge conda-build -y
conda develop /home/user/seamless
mamba remove seamless-framework -y
mamba install -c conda-forge -c rpbs seamless-framework --only-deps -y
```

- You can then use the commands in the current folder as drop-in replacements for the seamless-cli commands, without installing Docker.
NOTE: unlike seamless-cli-singularity/, the exported/used conda environments are NOT compatible with the ones exported by seamless-cli/seamless-conda-env-export.
