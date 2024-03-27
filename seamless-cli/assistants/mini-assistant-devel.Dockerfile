# syntax=docker/dockerfile:1
FROM seamless-devel
RUN pip install anyio
COPY mini-assistant.py .
CMD python -u mini-assistant.py --port $ASSISTANT_PORT --host $ASSISTANT_HOST
ENV PATH /seamless/bin:$PATH
HEALTHCHECK --interval=5s --timeout=2s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:$ASSISTANT_PORT/config || exit 1