FROM rpbs/seamless-deps
LABEL author="Sjoerd de Vries <sjoerd.de-vries@inserm.fr>"
USER root
RUN apt install less && conda install black mypy types-requests sphinx recommonmark -y && pip install sphinx_rtd_theme && echo 'export MYPYPATH=/seamless' >> /home/jovyan/.bashrc 
RUN chown -R jovyan /opt/conda && chmod -R a+w /opt/conda
COPY . /usr/local/src/seamless-tools
RUN rm -rf /usr/local/src/seamless-tools/.git && \
    mkdir /home/jovyan/software && \
    ln -s /seamless/seamless /home/jovyan/software/seamless && \
    ln -s /seamless/tests /home/jovyan/seamless-tests && \
    ln -s /seamless/examples /home/jovyan/seamless-examples && \
    cp -Lr /usr/local/src/seamless-tools/scripts /home/jovyan/seamless-scripts && \
    cp -Lr /usr/local/src/seamless-tools/tools /home/jovyan/seamless-tools
RUN chown -R jovyan /home/jovyan && chmod -R g=u /home/jovyan
RUN ln -s /seamless/seamless/graphs /seamless-graphs
ENV PYTHONPATH /home/jovyan/software:$PYTHONPATH
ENV XDG_CONFIG_HOME=/seamless