# syntax=docker/dockerfile:1
FROM seamless-devel
RUN pip install anyio
COPY micro-assistant.py .
CMD python -u mini-assistant.py --port $ASSISTANT_PORT --host $ASSISTANT_HOST
