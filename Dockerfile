FROM rpbs/seamless-deps:0.12
LABEL author="Sjoerd de Vries <sjoerd.devries@loria.fr>"
LABEL maintainer="Sjoerd de Vries <sjoerd.devries@loria.fr>"
LABEL version="0.12"
USER root
RUN apt update && apt install less gcc g++ gfortran libjpeg9 gettext -y  # gettext for seamless-mode
RUN cd /usr/local/src && apt install git -y && git clone https://github.com/sjdv1982/seamless.git --branch stable --depth 1 && rm seamless/.git -rf
RUN grep -v 'rpbs::seamless-framework' /usr/local/src/seamless/conda/seamless-exact-environment.yml > /tmp/ENV.yml
RUN mamba env update --name base --file /tmp/ENV.yml
COPY . /usr/local/src/seamless-tools
RUN rm -rf /usr/local/src/seamless-tools/.git && \
    mkdir /home/jovyan/software && \
    ln -s /usr/local/src/seamless/seamless /home/jovyan/software/seamless && \
    cp -Lr /usr/local/src/seamless/tests /home/jovyan/seamless-tests && \
    cp -Lr /usr/local/src/seamless/examples /home/jovyan/seamless-examples && \
    cp -Lr /usr/local/src/seamless-tools/scripts /home/jovyan/seamless-scripts && \
    cp -Lr /usr/local/src/seamless-tools/tools /home/jovyan/seamless-tools && \
    cp -Lr /usr/local/src/seamless-tools/seamless-cli /home/jovyan/seamless-cli && \
    cp -Lr /usr/local/src/seamless/bin /home/jovyan/seamless-bin
RUN chown -R jovyan /home/jovyan && chmod -R g=u /home/jovyan
RUN groupadd docker -g 999 && mkdir /seamless-pins
USER jovyan
RUN echo 'alias conda=mamba' >> /home/jovyan/.bashrc \
    && echo 'export PATH=~/seamless-cli:$PATH' >> /home/jovyan/.bashrc \
    && echo 'export PATH=~/seamless-bin:$PATH' >> /home/jovyan/.bashrc \
    && echo 'source activate-seamless-mode.sh' >> /home/jovyan/.bashrc
ENV PYTHONPATH /home/jovyan/software:$PYTHONPATH
HEALTHCHECK --interval=5s --timeout=2s --start-period=30s --retries=3 \
  CMD touch /cwd