FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pypdf python-docx

COPY rag_engine ./rag_engine

RUN useradd --create-home rag && mkdir -p /data/uploads && chown -R rag /data
USER rag

EXPOSE 8500
CMD ["python", "-m", "rag_engine.server", "--host", "0.0.0.0", "--port", "8500"]
