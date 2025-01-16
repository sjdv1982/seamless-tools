# syntax=docker/dockerfile:1
FROM seamless-devel
RUN pip install "dask[distributed]" 'distributed==2024.11.*' anyio 'tornado>=6.3' lz4 cloudpickle==3
COPY micro-dask-assistant.py .
CMD start.sh python -u micro-dask-assistant.py $DASK_SCHEDULER_ADDRESS --port $ASSISTANT_PORT --host $ASSISTANT_HOST
HEALTHCHECK --interval=5s --timeout=2s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:$ASSISTANT_PORT/config?agent=HEALTHCHECK || exit 1