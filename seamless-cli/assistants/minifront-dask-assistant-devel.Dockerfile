# syntax=docker/dockerfile:1
FROM seamless-devel
RUN pip install "dask[distributed]" anyio 'tornado>=6.3' lz4 cloudpickle==3
COPY minifront-dask-assistant.py .
CMD start.sh python -u minifront-dask-assistant.py $DASK_SCHEDULER_ADDRESS --port $ASSISTANT_PORT --host $ASSISTANT_HOST
