# Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY app.py .

RUN pip install flask

EXPOSE 8000

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=8000"]
