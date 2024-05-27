#!/bin/bash
set -u -e -x

comdir=../../seamless-cli
docdir=$comdir/doc
cd $RECIPE_DIR

cd $docdir
rm -rf man/build/*.1
seamless-run-no-webserver python3 man/build.py
cd man
ls build/*.1
cd $RECIPE_DIR

mkdir -p $PREFIX/bin
mkdir -p $PREFIX/share/seamless-cli/delegate
mkdir -p $PREFIX/share/seamless-cli/assistants
mkdir -p $PREFIX/share/seamless-cli/hashserver
mkdir -p $PREFIX/share/seamless-cli/database
mkdir -p $PREFIX/share/man/man1/

for i in $(cat filelist); do
  if [[ "$i" =~ '/' ]]
  then
    cp $comdir/$i $PREFIX/share/seamless-cli/$i
  else
    cp $comdir/$i $PREFIX/bin
    ii=$docdir/man/build/${i}.1
    if [ -f "$ii" ]; then
      cp $ii $PREFIX/share/man/man1/
    fi
  fi
done