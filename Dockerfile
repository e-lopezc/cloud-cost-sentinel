FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy the requirements first
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY src/ ./src/

# Set the python path
ENV PYTHONPATH=/app

# Run the analyzer
CMD ["python", "src/main.py"]
