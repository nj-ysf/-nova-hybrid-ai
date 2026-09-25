FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home chatbot
COPY --chown=chatbot:chatbot chatbot /app/chatbot
USER chatbot
WORKDIR /app/chatbot
EXPOSE 8000
CMD ["gunicorn", "chatbot.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "240"]
