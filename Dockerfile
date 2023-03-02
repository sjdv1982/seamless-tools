FROM rpbs/seamless-deps:0.11
LABEL author="Sjoerd de Vries <sjoerd.de-vries@inserm.fr>"
LABEL maintainer="Sjoerd de Vries <sjoerd.de-vries@inserm.fr>"
LABEL version="0.11"
USER root
RUN cd /usr/local/src && apt install git -y && git clone https://github.com/sjdv1982/seamless.git --branch stable --depth 1 && rm seamless/.git -rf
RUN mamba env update --name base --file /usr/local/src/seamless/conda/seamless-exact-environment.yml
COPY . /usr/local/src/seamless-tools
RUN rm -rf /usr/local/src/seamless-tools/.git && \
    mkdir /home/jovyan/software && \
    cp -Lr /usr/local/src/seamless/tests /home/jovyan/seamless-tests && \
    cp -Lr /usr/local/src/seamless/examples /home/jovyan/seamless-examples && \
    cp -Lr /usr/local/src/seamless-tools/scripts /home/jovyan/seamless-scripts && \
    cp -Lr /usr/local/src/seamless-tools/tools /home/jovyan/seamless-tools && \
    ln -s /opt/conda/lib/python3.10/site-packages/seamless /home/jovyan/software/seamless && \
    ln -s /opt/conda/lib/python3.10/site-packages/seamless/graphs /seamless-graphs
RUN chown -R jovyan /home/jovyan && chmod -R g=u /home/jovyan
USER jovyan
RUN echo 'alias conda=mamba' >> /home/jovyan/.bashrc
