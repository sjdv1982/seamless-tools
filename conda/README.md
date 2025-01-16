How to build the CLI Conda packages
===================================

The following conda packages are being built:

- seamless-cli. The full command line tool package from ../seamless-cli .
    Invokes Docker, calling the underlying tools from the rpbs/seamless Docker image.
- seamless-cli-bin. A re-implementation of a subset of seamless-cli,
    which does not invoke Docker, but calls the underlying tools directly.
    The following tools are unique to seamless-cli-bin: seamless-fairdir-add-distribution seamless-fairdir-build, seamless-multi, seamless-queue, seamless-queue-finish
- seamless-scripts. The underlying tools invoked by seamless-cli-bin
- seamless-cli-complement. The subset of seamless-cli that is *not* in seamless-cli-bin.

In principle, a working Seamless installation contains either seamless-cli + rpbs/seamless Docker image  
OR seamless-framework + seamless-cli-bin + seamless-cli-complement + rpbs/seamless Docker image (for the complement).

1. Use the same versioning/tag as for Seamless itself.

2. Update the version number in `*/meta.yaml`. Git commit and tag.

3. If you didn't do already, create a conda environment to build and upload conda environments: `mamba create -n seamless-build -c conda-forge -c rpbs -c main silk seamless-cli anaconda-client conda-build -y`

4. Do `conda activate seamless-build`. In case of `seamless-cli-bin`, go to /seamless/conda instead.

5. Then launch `conda build -c conda-forge seamless-cli`.
In case of `seamless-cli-bin` and `seamless-scripts`, do `conda build -c conda-forge -c rpbs ...`. Note the output file (.tar.bz2).
If you forget it, run `conda build ... --output`

*5a. Alternively, you can install and use `rattler-build`. It has a slightly different `meta.yaml` file called `recipe.yaml`. The command is as follows*:

```bash
cd seamless-cli
rattler-build build --output-dir /tmp/
```

*And you will find the $filename.tar.bz2 file as /tmp/noarch/$filename.conda.*
***NOTE: As of May 2024, this generates a deficient package with no dependencies. Anaconda refuses to accept it.***

6. Upload to anaconda:

```
anaconda login
anaconda upload $filename.tar.bz2
```
