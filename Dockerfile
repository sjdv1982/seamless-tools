FROM rpbs/seamless-deps:0.10
LABEL author="Sjoerd de Vries <sjoerd.de-vries@inserm.fr>"
LABEL maintainer="Sjoerd de Vries <sjoerd.de-vries@inserm.fr>"
LABEL version="0.10"
USER root
RUN cd /usr/local/src && git clone https://github.com/sjdv1982/seamless.git --branch stable --depth 1 && rm seamless/.git -rf
RUN conda config --env --set channel_priority strict && conda env update --name base --file /usr/local/src/seamless/conda/seamless-framework-environment.yml
RUN chown -R jovyan /opt/conda && chmod -R a+w /opt/conda
COPY . /usr/local/src/seamless-tools
RUN rm -rf /usr/local/src/seamless-tools/.git && \
    mkdir /home/jovyan/software && \
    cp -Lr /usr/local/src/seamless/tests /home/jovyan/seamless-tests && \
    cp -Lr /usr/local/src/seamless/examples /home/jovyan/seamless-examples && \
    cp -Lr /usr/local/src/seamless-tools/scripts /home/jovyan/seamless-scripts && \
    cp -Lr /usr/local/src/seamless-tools/tools /home/jovyan/seamless-tools && \
    ln -s /opt/conda/lib/python3.8/site-packages/seamless /home/jovyan/software/seamless
RUN chown -R jovyan /home/jovyan && chmod -R g=u /home/jovyan
RUN ln -s /opt/conda/lib/python3.8/site-packages/seamless/graphs /seamless-graphs