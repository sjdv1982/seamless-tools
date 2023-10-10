# syntax=docker/dockerfile:1
FROM rpbs/seamless
COPY micro-assistant.py .
CMD start.sh python -u micro-assistant.py --port $ASSISTANT_PORT --host $ASSISTANT_HOST
