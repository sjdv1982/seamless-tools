# syntax=docker/dockerfile:1
FROM seamless-devel
RUN mamba install -c conda-forge dask anyio
COPY mini-dask-assistant.py .
CMD python -u mini-dask-assistant.py $DASK_SCHEDULER_ADDRESS --port $ASSISTANT_PORT --host $ASSISTANT_HOST
