# syntax=docker/dockerfile:1
FROM seamless-devel
RUN pip install "dask[distributed]" anyio 'tornado>=6.3'
COPY mini-dask-assistant.py .
CMD start.sh python -u mini-dask-assistant.py $DASK_SCHEDULER_ADDRESS --port $ASSISTANT_PORT --host $ASSISTANT_HOST
