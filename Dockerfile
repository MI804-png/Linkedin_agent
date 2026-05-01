# Playwright base image – has Chromium + all system deps pre-installed
FROM mcr.microsoft.com/playwright/python:v1.53.0-noble

WORKDIR /app

# Copy the bot source
COPY linkedin_bot/ ./linkedin_bot/
# Copy the webapp
COPY webapp/ ./webapp/

# Install webapp Python deps
RUN pip install --no-cache-dir -r webapp/requirements.txt

# Install Playwright browser (chromium only)
RUN playwright install chromium

# Create folders the app expects
RUN mkdir -p webapp/uploads webapp/user_data

# Expose Flask port
EXPOSE 5000

# Start gunicorn pointing at the webapp package
CMD ["gunicorn", "--chdir", "webapp", "app:app", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--preload"]
