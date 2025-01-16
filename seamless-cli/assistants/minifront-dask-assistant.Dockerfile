# syntax=docker/dockerfile:1
FROM rpbs/seamless:0.13
RUN pip install "dask[distributed]" 'distributed==2024.11.*' anyio 'tornado>=6.3' lz4 cloudpickle==3
COPY minifront-dask-assistant.py .
CMD start.sh python -u minifront-dask-assistant.py $DASK_SCHEDULER_ADDRESS --port $ASSISTANT_PORT --host $ASSISTANT_HOST
HEALTHCHECK --interval=5s --timeout=2s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:$ASSISTANT_PORT/config?agent=HEALTHCHECK || exit 1