# syntax=docker/dockerfile:1
FROM seamless-devel
COPY micro-assistant.py .
CMD python -u micro-assistant.py --port $ASSISTANT_PORT --host $ASSISTANT_HOST
