% seamless-jupyter(1) Version 0.1 | seamless-cli Documentation

NAME
====

**seamless-jupyter-safe** - Starts a Jupyter Notebook server in a new Seamless Docker container

SYNOPSIS
========

| **seamless-jupyter-safe** \[_Jupyter notebook server arguments_]
| **seamless-jupyter-safe** \[**-h**|**--help**]

DESCRIPTION
===========

Starts a Jupyter Notebook server in a new Seamless Docker container

The current directory is mounted to /cwd, and the Jupyter server is executed there

/tmp is mounted as well

**NOTE: The new container does not have access to the Docker daemon. Bash-docker transformers cannot be executed, and most seamless-cli commands will not work.**

**NOTE: The new container claims the default ports for the Seamless web server, as well as port 8888 for Jupyter.**

All Jupyter passwords are disabled.

By default, only connections from `localhost` are accepted.
Add `--ip='0.0.0.0'` to allow connections from outside.

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

**seamless-jupyter(1)**