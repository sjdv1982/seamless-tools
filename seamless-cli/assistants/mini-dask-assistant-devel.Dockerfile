# syntax=docker/dockerfile:1
FROM seamless-devel
RUN pip install "dask[distributed]" 'distributed>=2024.5.2' anyio 'tornado>=6.3' lz4 cloudpickle==3
COPY mini-dask-assistant.py .
CMD python -u mini-dask-assistant.py $DASK_SCHEDULER_ADDRESS --port $ASSISTANT_PORT --host $ASSISTANT_HOST
HEALTHCHECK --interval=5s --timeout=2s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:$ASSISTANT_PORT/config || exit 1