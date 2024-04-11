% seamless-ipython(1) Version 0.1 | seamless-cli Documentation

NAME
====

**seamless-ipython-safe** - Starts an IPython shell in a new Seamless Docker container

SYNOPSIS
========

| **seamless-ipython-safe** \[_IPython arguments_]
| **seamless-ipython-safe** \[**-h**|**--help**]

DESCRIPTION
===========

Starts an IPython shell in a new Seamless Docker container

The current directory is mounted to /cwd, and IPython is executed there.

/tmp is mounted as well

**NOTE: The new container does not have access to the Docker daemon. Bash-docker transformers cannot be executed, and most seamless-cli commands will not work.**

**NOTE: The new container claims the default ports for the Seamless web server. Use seamless-ipython-safe-no-webserver to avoid this.**


Options
-------

-h, --help

:   Prints brief usage information.


BUGS
====

See GitHub Issues: <https://github.com/sjdv1982/seamless/issues>

AUTHOR
======

Sjoerd de Vries <sjdv1982@gmail.com>

SEE ALSO
========

**seamless-ipython(1)**, **seamless-bash(1)**, **seamless-jupyter(1)**