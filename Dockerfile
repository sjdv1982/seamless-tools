FROM rpbs/seamless-deps
LABEL author="Sjoerd de Vries <sjoerd.de-vries@inserm.fr>"
LABEL version="0.8"
USER root
COPY . /usr/local/src/seamless
RUN conda config --env --set channel_priority strict && conda env update --name base --file /usr/local/src/seamless/conda/seamless-framework-environment.yml
RUN rm -rf /usr/local/src/seamless/.git && \
    mkdir /home/jovyan/software && \
    cp -Lr /usr/local/src/seamless/seamless /home/jovyan/software/seamless && \
    cp -Lr /usr/local/src/seamless/tests /home/jovyan/seamless-tests && \
    cp -Lr /usr/local/src/seamless/examples /home/jovyan/seamless-examples && \
    cp -Lr /usr/local/src/seamless/scripts /home/jovyan/seamless-scripts && \
    cp -Lr /usr/local/src/seamless/tools /home/jovyan/seamless-tools
RUN chown -R jovyan /home/jovyan && chmod -R g=u /home/jovyan
ENV PYTHONPATH /home/jovyan/software:$PYTHONPATH
