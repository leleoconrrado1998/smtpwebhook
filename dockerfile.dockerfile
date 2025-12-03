FROM python:3.11-slim

WORKDIR /app

# Instala dependências
RUN pip install --no-cache-dir requests

# Copia script
COPY smtpwebhook.py .

# Roda o script
CMD ["python", "-u", "smtpwebhook.py"]
