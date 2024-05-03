FROM rpbs/seamless-deps:0.12
LABEL author="Sjoerd de Vries <sjoerd.devries@loria.fr>"
LABEL maintainer="Sjoerd de Vries <sjoerd.devries@loria.fr>"
LABEL version="0.12"
USER root
RUN apt update && apt install less gcc g++ gfortran libjpeg9 -y
RUN cd /usr/local/src && apt install git -y && git clone https://github.com/sjdv1982/seamless.git --branch stable --depth 1 && rm seamless/.git -rf
RUN mamba env update --name base --file /usr/local/src/seamless/conda/seamless-exact-environment.yml
COPY . /usr/local/src/seamless-tools
RUN rm -rf /usr/local/src/seamless-tools/.git && \
    mkdir /home/jovyan/software && \
    cp -Lr /usr/local/src/seamless/tests /home/jovyan/seamless-tests && \
    cp -Lr /usr/local/src/seamless/examples /home/jovyan/seamless-examples && \
    cp -Lr /usr/local/src/seamless-tools/scripts /home/jovyan/seamless-scripts && \
    cp -Lr /usr/local/src/seamless-tools/tools /home/jovyan/seamless-tools && \
    ln -s /opt/conda/lib/python3.10/site-packages/seamless /home/jovyan/software/seamless
RUN chown -R jovyan /home/jovyan && chmod -R g=u /home/jovyan
USER jovyan
RUN echo 'alias conda=mamba' >> /home/jovyan/.bashrc
HEALTHCHECK --interval=5s --timeout=2s --start-period=30s --retries=3 \
  CMD touch /cwd