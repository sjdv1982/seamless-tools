% seamless-bash(1) Version 0.1 | seamless-cli Documentation

NAME
====

**seamless-bash** - Starts a bash shell in a new Seamless Docker container

SYNOPSIS
========

| **seamless-bash**

DESCRIPTION
===========

Starts a bash shell in a new Seamless Docker container

The ID of the Docker container is available to the Docker container itself,
 in the file ~/DOCKER_CONTAINER.

The current directory is mounted to /cwd, and the command is executed there
The name of the current directory is available in the container as $HOSTCWD.

**NOTE: The new container has access to the Docker daemon. This is a security risk. Use seamless-bash-safe to avoid this.**

**NOTE: The new container claims the default ports for the Seamless web server. Use seamless-bash-no-webserver to avoid this.**
.
BUGS
====

See GitHub Issues: <https://github.com/sjdv1982/seamless/issues>

AUTHOR
======

Sjoerd de Vries <sjdv1982@gmail.com>

SEE ALSO
========

**seamless-bash-safe(1)**, **seamless-ipython(1)**, **seamless-jupyter(1)**