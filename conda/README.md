How to build the CLI Conda packages
===================================

1. Use the same versioning/tag as for Seamless itself.

2. Update the version number in `*/meta.yaml`. Git commit and tag.

3. From here, do `conda activate seamless` and then launch `conda build seamless-cli`. Note the output file (.tar.bz2).
If you forget it, run `conda build seamless-cli --output`

4. Upload to anaconda:
```
anaconda login
anaconda upload $filename.tar.bz2
```