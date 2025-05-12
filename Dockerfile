FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y docker.io

# Set default port that can be overridden
ENV PORT=8000

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
