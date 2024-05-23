How to build the CLI Conda packages
===================================

1. Use the same versioning/tag as for Seamless itself.

2. Update the version number in `*/meta.yaml`. Git commit and tag.

3. If you didn't do already, create a conda environment to build and upload conda environments: `mamba create -n seamless-build -c conda-forge -c rpbs -c main silk seamless-cli anaconda-client conda-build -y`

4. From here, do `conda activate seamless-build`. Then launch `conda build -c conda-forge seamless-cli`. Note the output file (.tar.bz2).
If you forget it, run `conda build seamless-cli --output`

4a. Alternively, you can install and use `rattler-build`. It has a slightly different `meta.yaml` file called `recipe.yaml`. The command is as follows: 

```bash
cd seamless-cli
rattler-build build --output-dir /tmp/
```
And you will find the $filename.tar.bz2 file as /tmp/noarch/$filename.conda.
NOTE: As of May 2024, this generates a deficient package with no dependencies. Anaconda refuses to accept it.

5. Upload to anaconda:

```
anaconda login
anaconda upload $filename.tar.bz2
```