# syntax=docker/dockerfile:1
FROM rpbs/seamless:0.13
COPY mini-assistant.py .
CMD start.sh python -u mini-assistant.py --port $ASSISTANT_PORT --host $ASSISTANT_HOST
HEALTHCHECK --interval=5s --timeout=2s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:$ASSISTANT_PORT/config?agent=HEALTHCHECK || exit 1