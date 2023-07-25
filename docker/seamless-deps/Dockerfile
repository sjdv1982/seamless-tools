FROM jupyter/base-notebook@sha256:28be88ef3ea6a49c84d11489b2f9674d65806daa439e8b3ab3aeba4c1cd8cb66
LABEL author="Sjoerd de Vries <sjdv1982@gmail.com>"
LABEL maintainer="Sjoerd de Vries <sjdv1982@gmail.com>"
USER root
RUN apt update && apt install -y curl gdb iputils-ping apt-transport-https gnupg-agent lshw 
RUN sudo mkdir -m 0755 -p /etc/apt/keyrings \
   && curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
   && echo \
   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
jammy stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null \
   && sudo apt update && sudo apt install -y docker-ce-cli
USER jovyan
RUN /opt/conda/bin/conda init
COPY docker/seamless-deps-environment.yml seamless-deps-environment.yml
RUN source ~/.bashrc && mamba env update --name base --file seamless-deps-environment.yml
