# syntax=docker/dockerfile:1
FROM python:3.10-alpine
RUN pip install aiohttp peewee
COPY database.py .
CMD python database.py /database/seamless.db --port $DATABASE_PORT --host $DATABASE_HOST