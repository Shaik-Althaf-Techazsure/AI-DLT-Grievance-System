#!/bin/sh
# Wait for the database container to be ready on port 3306 (internal Docker port)
echo "Waiting for MariaDB to start on db:3306..."

# Loop until MariaDB is accepting TCP connections
until nc -z db 3306; do
  echo "MariaDB is unavailable - sleeping"
  sleep 2
done

echo "MariaDB is ready! Starting Flask app..."

# Execute the Gunicorn command (same as your docker-compose command)
exec gunicorn --bind 0.0.0.0:5000 app:app
