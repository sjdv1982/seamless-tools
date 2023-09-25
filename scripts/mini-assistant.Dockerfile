# syntax=docker/dockerfile:1
FROM rpbs/seamless
COPY mini-assistant.py .
CMD python -u mini-assistant.py --port $ASSISTANT_PORT --host $ASSISTANT_HOST