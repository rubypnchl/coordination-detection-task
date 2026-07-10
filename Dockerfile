FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY README.md .
COPY prompts.txt .

# Data should be mounted or copied into /app/data before running.
# Example:
# docker run --rm -v "%cd%/data:/app/data" -v "%cd%/outputs:/app/outputs" coordination-task --split eval

ENTRYPOINT ["python", "src/16_score_candidates_and_results.py"]