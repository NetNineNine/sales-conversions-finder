FROM python:3.10-alpine
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
EXPOSE 8086
ENTRYPOINT [ "./app.py" ]
# CMD [ "app:app", "--port", "8000", "--host", "0.0.0.0" ]

# TODO: Add healthcheck
