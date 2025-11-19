FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.9.1+cpu --index-url https://download.pytorch.org/whl/cpu
RUN pip install -r requirements.txt

COPY llm_svc.py .

EXPOSE 8000

CMD ["uvicorn", "llm_svc:app", "--host", "0.0.0.0", "--port", "8000"]
