FROM jupyter/base-notebook@sha256:ae616b39021e6e2bd7a645f9ef8a802b1f5133bfa19f5ee4477de4a4d33f38e7
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
RUN pip install zstandard --force-reinstall
RUN pip install jsonschema==4.18.* requests==2.31.*