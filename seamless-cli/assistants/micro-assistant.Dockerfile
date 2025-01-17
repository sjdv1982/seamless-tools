# syntax=docker/dockerfile:1
FROM rpbs/seamless:0.14
COPY micro-assistant.py .
CMD start.sh python -u micro-assistant.py --port $ASSISTANT_PORT --host $ASSISTANT_HOST
HEALTHCHECK --interval=5s --timeout=2s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:$ASSISTANT_PORT/config?agent=HEALTHCHECK || exit 1