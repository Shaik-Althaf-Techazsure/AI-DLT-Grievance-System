FROM python:3.12.0

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies needed for pymysql (mysqlclient), netcat (nc command), and gcc (compiler)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    gcc \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files (including app.py and HTML templates)
COPY . /usr/src/app/

# CRITICAL FIX: Make the entrypoint script executable
COPY docker-entrypoint.sh /usr/src/app/docker-entrypoint.sh
RUN chmod +x /usr/src/app/docker-entrypoint.sh

# Use the shell script as the entry point. This script handles the database wait 
# and then executes the Gunicorn server.
ENTRYPOINT ["/usr/src/app/docker-entrypoint.sh"]
