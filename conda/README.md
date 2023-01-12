How to build the CLI Conda packages
===================================

1. Use the same versioning/tag as for Seamless itself.

2. Update the version number in `*/meta.yaml`. Git commit and tag.

3. If you didn't do already, create a conda environment to build and upload conda environments: `mamba create -n seamless-build -c conda-forge -c rpbs -c main silk seamless-cli anaconda-client conda-build -y`

4. From here, do `conda activate seamless-build`. Then launch `conda build seamless-cli`. Note the output file (.tar.bz2).
If you forget it, run `conda build seamless-cli --output`

4. Upload to anaconda:

```
anaconda login
anaconda upload $filename.tar.bz2
```