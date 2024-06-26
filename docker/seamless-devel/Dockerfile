FROM rpbs/seamless-deps
LABEL author="Sjoerd de Vries <sjoerd.devries@loria.fr>"
USER root
# gettext for seamless-mode
RUN apt update && apt install less gcc g++ gfortran libjpeg9 gettext -y && mamba install black mypy types-requests sphinx recommonmark -y && pip install sphinx_rtd_theme 
COPY ./scripts /usr/local/src/seamless-tools/scripts 
COPY ./tools /usr/local/src/seamless-tools/tools
COPY ./seamless-cli /usr/local/src/seamless-tools/seamless-cli
RUN rm -rf /usr/local/src/seamless-tools/.git && \
    mkdir /home/jovyan/software && \
    ln -s /seamless/seamless /home/jovyan/software/seamless && \
    ln -s /seamless/tests /home/jovyan/seamless-tests && \
    ln -s /seamless/examples /home/jovyan/seamless-examples && \
    cp -Lr /usr/local/src/seamless-tools/scripts /home/jovyan/seamless-scripts && \
    cp -Lr /usr/local/src/seamless-tools/tools /home/jovyan/seamless-tools && \
    cp -Lr /usr/local/src/seamless-tools/seamless-cli /home/jovyan/seamless-cli
RUN chown -R jovyan /home/jovyan && chmod -R g=u /home/jovyan
RUN mamba install -c rpbs silk -y
RUN groupadd docker -g 999 && mkdir /seamless-pins
USER jovyan
RUN echo 'export MYPYPATH=/seamless' >> /home/jovyan/.bashrc \
    && echo 'alias conda=mamba' >> /home/jovyan/.bashrc \
    && echo 'export PATH=~/seamless-cli:$PATH' >> /home/jovyan/.bashrc \
    && echo 'export PATH=~/seamless-bin:$PATH' >> /home/jovyan/.bashrc \
    && echo 'source activate-seamless-mode.sh' >> /home/jovyan/.bashrc
ENV XDG_CONFIG_HOME=/seamless
ENV PYTHONPATH /home/jovyan/software:$PYTHONPATH
HEALTHCHECK --interval=5s --timeout=2s --start-period=30s --retries=3 \
  CMD touch /cwd