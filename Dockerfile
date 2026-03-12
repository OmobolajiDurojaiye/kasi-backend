# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8000 (or whatever port Flask runs on)
EXPOSE 8000

# Define environment variables (these will be overridden by docker-compose or .env)
ENV FLASK_APP=run.py
ENV FLASK_ENV=production

# Run the backend when the container launches using gunicorn (better than plain Flask for production)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "run:app"]
