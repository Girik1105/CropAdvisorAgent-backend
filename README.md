# CropAdvisor Backend

Django + DRF backend for the CropAdvisor autonomous AI agent. A farmer texts a phone number and receives a specific, costed action plan for their field.

## Setup

```bash
# Activate the shared venv (one level up)
source ../venv/bin/activate

# Install dependencies
pip install django djangorestframework

# Run migrations
python manage.py migrate

# Start dev server
python manage.py runserver
```

## Project Structure

- `config/` — Django project settings and root URL config
- `agent/` — Core agent app (Gemini orchestration, models, API views)
- `tools/` — Data tool app (weather, crop health, soil, voice)
- `webhooks/` — Twilio SMS/WhatsApp webhook handler
