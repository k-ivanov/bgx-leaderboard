FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .

# Copy data directory (adjust path as needed)
COPY data ./data

# Expose port
EXPOSE 5001

# Set environment variables
ENV PORT=5001
ENV HOST=0.0.0.0

# Run the application
CMD ["python", "main.py"]

