# CropAdvisor Backend

Gemini-powered autonomous agricultural AI agent built for Innovation Hacks 2.0 (Google Track). Farmers text a phone number or use the dashboard and receive specific, costed action plans for their fields — the agent gathers data, reasons, and decides autonomously.

**Demo:** Cotton farmer near Casa Grande, AZ texts "How's my field looking?" → Agent calls 7 tools (live weather, real USDA soil, NASA POWER ET₀, NDVI, market prices, pest risk, growth stage) → Gemini reasons through 3-agent pipeline → Responds: "Your cotton is under drought stress. Irrigate within 24 hours. Cost: $280. Delaying risks 15% yield loss."

**Real data sources:** OpenWeatherMap (live weather), USDA SSURGO (real soil profiles by GPS), NASA POWER (satellite evapotranspiration for water budgets), NDVI vegetation index (pre-fetched from USGS/Landsat).

## Quick Start

```bash
# 1. Activate venv (from parent CropAdvisor/ directory)
source ../venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up .env (fill in your API keys — see below)
cp .env.example .env

# 4. Run migrations
python manage.py migrate

# 5. Seed demo data (3 fields, NDVI — soil fetched live from USDA)
python manage.py seed_demo

# 6. Start server
python manage.py runserver

# 7. Run the full demo (6 scenarios through Gemini + real APIs)
python manage.py run_demo
```

The API is available at `http://127.0.0.1:8000/api/v1/`.

## Environment Variables

Create a `.env` file in the project root:

```env
# Django
SECRET_KEY=your-secret-key
DEBUG=True

# Frontend (CORS)
FRONTEND_URL=http://localhost:3000

# Database (optional — falls back to SQLite if not set)
POSTGRES_DB=cropadvisor
POSTGRES_PASSWORD=cropadvisor
POSTGRES_USER=cropadvisor
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Gemini API (REQUIRED for agent)
GEMINI_API_KEY=your-gemini-key

# OpenWeatherMap (optional — falls back to static data)
OPENWEATHERMAP_API_KEY=your-key

# Twilio (for SMS)
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx

# ElevenLabs (for voice)
ELEVENLABS_API_KEY=your-key
```

**Where to get keys:**
- Gemini: [aistudio.google.com](https://aistudio.google.com/) → Get API Key
- OpenWeatherMap: [openweathermap.org/api](https://openweathermap.org/api) → Sign up → API Keys
- Twilio: [console.twilio.com](https://console.twilio.com/) → Account SID + Auth Token
- ElevenLabs: [elevenlabs.io](https://elevenlabs.io/) → Profile → API Keys

## Management Commands

### `seed_demo` — Populate demo data

```bash
python manage.py seed_demo              # Seed user + 3 fields + environmental data
python manage.py seed_demo --run-agent  # Seed + run agent on first field
python manage.py seed_demo --reset      # Wipe everything and re-seed
```

Creates:
- **User:** `demo_farmer` / `demo1234!`
- **Fields:** North 40 Cotton (40ac, NDVI 0.38), Mesa Citrus Grove (15ac, NDVI 0.72), Chandler Alfalfa (60ac, NDVI 0.29)
- **Per field:** NDVI crop health record (soil and weather are NOT pre-seeded — agent fetches real data from USDA SSURGO and OpenWeatherMap on first run)

### `run_demo` — Full demo script (hits Gemini API)

```bash
python manage.py run_demo                  # Run all 6 scenarios (~3-5 min)
python manage.py run_demo --scenario 1     # Run just one scenario
python manage.py run_demo --skip-seed      # Use existing data
python manage.py run_demo --reset          # Wipe + re-seed + run all
```

**6 Demo Scenarios:**

| # | Scenario | Field | What it tests | Real data sources |
|---|----------|-------|---------------|-------------------|
| 1 | Cotton Drought Emergency | North 40 (NDVI 0.38) | Full 7-tool pipeline → irrigate | OpenWeatherMap, USDA SSURGO, NASA POWER |
| 2 | Citrus Grove Check-in | Mesa Citrus (NDVI 0.72) | Healthy field → monitor/no action | OpenWeatherMap, USDA SSURGO, NASA POWER |
| 3 | Alfalfa Nitrogen Crisis | Chandler Alfalfa (NDVI 0.29) | Severe stress → fertilize + market ROI | OpenWeatherMap, USDA SSURGO, NASA POWER |
| 4 | General Question | — | Intent classifier → QA path (no tools) | None (pure Gemini reasoning) |
| 5 | SMS Water Cost | North 40 via SMS | SMS channel + NASA POWER water budget | NASA POWER ET₀ calculation |
| 6 | Pest Alert | North 40 | Live weather → pest risk rules | OpenWeatherMap → rule engine |

Outputs a formatted table with action, urgency, cost, tools called, timing, and data sources per scenario.

## Project Structure

```
├── config/                  # Django project settings, URLs, WSGI
├── accounts/                # Auth (signup, login, JWT tokens)
│   ├── models.py            # UserProfile (phone number)
│   ├── serializers.py       # SignupSerializer
│   └── views.py             # SignupView
├── agent/                   # Core agent app
│   ├── models.py            # Field, AgentSession, AgentMessage, ActionRecommendation,
│   │                        # WeatherSnapshot, CropHealthRecord, SoilProfile,
│   │                        # MarketSnapshot, PestRiskAssessment, WaterUsageEstimate
│   ├── engine.py            # CropAdvisorEngine — intent routing + 3-agent pipeline
│   ├── prompts.py           # System prompts (field agent, orchestrator, recommender,
│   │                        # intent classifier, general QA)
│   ├── serializers.py       # DRF serializers for all models
│   ├── views.py             # Agent message, trace, field CRUD, data history views
│   ├── urls.py              # /agent/message/, /agent/trace/
│   ├── urls_fields.py       # /fields/, /fields/<id>/sessions|weather|crop-health|soil/
│   └── management/commands/ # seed_demo.py, run_demo.py
├── tools/                   # Data tools (7 functions)
│   ├── services.py          # get_weather, get_crop_health, get_soil_profile,
│   │                        # get_market_prices, get_pest_risk, get_water_usage,
│   │                        # get_growth_stage
│   ├── views.py             # Tool API endpoints (AllowAny, for debugging)
│   └── urls.py              # /tools/weather/, /tools/crop-health/, /tools/soil/
├── webhooks/                # Twilio SMS webhook
│   ├── views.py             # SmsWebhookView (returns TwiML)
│   └── urls.py              # /webhook/sms/
├── API_DOCS/                # Team documentation
│   ├── FRONTEND_GUIDE.md    # Next.js integration with all endpoints
│   ├── TWILIO_GUIDE.md      # SMS webhook setup
│   └── AGENT_ARCHITECTURE.md # Agent pipeline internals
├── Procfile                 # Heroku deployment
├── runtime.txt              # Python version for Heroku
├── requirements.txt
├── .env                     # Environment variables (not committed)
└── manage.py
```

## Agent Architecture

### Intent Classification

Every message first goes through an intent classifier (quick Gemini call):
- **"action_needed"** → Full 7-tool pipeline (Field Agent → Orchestrator → Recommender)
- **"general_question"** → Lightweight QA agent with field context (no tools)

### Full Pipeline (action_needed)

```
Farmer Message
    ↓
Intent Classifier → "action_needed"
    ↓
Field Agent (gathers data from 7 tools autonomously)
    ├── get_weather(lat, lng)           → LIVE from OpenWeatherMap API
    ├── get_crop_health(field_id)       → NDVI from DB (real USGS/Landsat source)
    ├── get_soil_profile(field_id)      → REAL from USDA SSURGO API by GPS coords
    ├── get_market_prices(crop_type)    → Commodity prices (USDA-sourced static)
    ├── get_pest_risk(crop, temp, hum)  → Rule engine using LIVE weather conditions
    ├── get_water_usage(field_id)       → NASA POWER satellite ET₀ + FAO Penman-Monteith
    └── get_growth_stage(crop_type)     → Calendar-based with month-specific guidance
    ↓
Orchestrator Agent (analyzes all data, creates action plan)
    ↓
Recommender Agent (generates costed recommendation with steps)
    ↓
Response + ActionRecommendation saved to DB
```

### QA Pipeline (general_question)

```
Farmer Message
    ↓
Intent Classifier → "general_question"
    ↓
General QA Agent (answers with field context, no tool calls)
    ↓
Response (no structured recommendation)
```

### Two Entry Points, Same Engine

| Entry | Auth | How it works |
|-------|------|-------------|
| Dashboard (`POST /agent/message/`) | JWT | User selects field, sends message |
| SMS (`POST /webhook/sms/`) | None | Twilio POSTs, field looked up by phone number |

Both run `CropAdvisorEngine.run()` — identical pipeline.

## Data Models

All models use UUID primary keys and are in `agent/models.py`.

### Core Models

| Model | Purpose |
|-------|---------|
| **Field** | Registered crop field (name, crop, coordinates, area, soil, phone) |
| **AgentSession** | Conversation session (user, field, channel: sms/dashboard) |
| **AgentMessage** | Messages in a session (user input, tool calls, agent outputs) |
| **ActionRecommendation** | Structured recommendation (action, urgency, cost, risk, steps) |

### Environmental Data (saved per agent run)

| Model | Purpose | Source | When Created |
|-------|---------|--------|-------------|
| **WeatherSnapshot** | Temperature, humidity, wind, precipitation forecast | OpenWeatherMap API (live) | Every agent run |
| **CropHealthRecord** | NDVI score, stress level, vegetation trend | USGS/Landsat (pre-fetched) | First run (or updated) |
| **SoilProfile** | pH, drainage, water capacity, organic matter | USDA SSURGO API (real, by GPS) | First run (one-to-one, cached) |
| **MarketSnapshot** | Commodity price, trend, seasonal outlook | Static (USDA-sourced) | Every agent run |
| **PestRiskAssessment** | Risk level, threats, preventive actions | Rule engine + live weather | Every agent run |
| **WaterUsageEstimate** | Daily water need, deficit, irrigation cost | NASA POWER ET₀ + FAO Penman-Monteith | Every agent run |

## API Endpoints

All prefixed with `/api/v1/`.

### Authentication (no auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup/` | Register + get JWT tokens |
| POST | `/auth/login/` | Login + get JWT tokens |
| POST | `/auth/token/refresh/` | Refresh access token |

### Agent (JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agent/message/` | Send message, run agent pipeline |
| GET | `/agent/trace/<session_id>/` | Full reasoning trace (messages + recommendations) |

### Fields (JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/fields/` | List user's fields |
| POST | `/fields/` | Create a field |
| GET/DELETE | `/fields/<id>/` | Get or delete a field |
| GET | `/fields/<id>/sessions/` | Sessions for a field |
| GET | `/fields/<id>/weather/` | Weather snapshot history |
| GET | `/fields/<id>/crop-health/` | NDVI record history |
| GET | `/fields/<id>/soil/` | Soil profile |

### Tools (no auth — debug/display)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tools/weather/?lat=&lng=` | Live weather data |
| GET | `/tools/crop-health/?field_id=` | NDVI data |
| GET | `/tools/soil/?field_id=` | Soil data |

### Webhook (no auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhook/sms/` | Twilio inbound SMS → TwiML response |

## Tech Stack

| Layer | Technology | Data Source |
|-------|-----------|-------------|
| Framework | Django 5.2 + Django REST Framework | — |
| Auth | SimpleJWT (30min access / 7-day refresh) | — |
| AI Agent | Gemini 2.5 Flash via google-genai SDK | Google AI |
| Weather | OpenWeatherMap API | **Live** — current + 5-day forecast |
| Soil | USDA SSURGO via Soil Data Access API | **Real** — queried by GPS coordinates |
| Water Budget | NASA POWER + FAO Penman-Monteith ET₀ | **Satellite** — solar radiation, temp, wind, humidity |
| Crop Health | NDVI vegetation index | Pre-fetched from real USGS/Landsat data |
| Market Prices | Commodity exchange data | Static (realistic USDA-sourced values) |
| Pest Risk | Rule-based engine | Uses **live weather** conditions + crop type |
| Growth Stage | Crop calendar | Month-specific guidance per crop |
| SMS | Twilio (webhook → TwiML) | — |
| Voice | ElevenLabs TTS | — |
| Database | PostgreSQL (prod) / SQLite (dev) | — |
| Hosting | Heroku (gunicorn + whitenoise) | — |

## Deployment (Heroku)

The project includes `Procfile` and `runtime.txt` for Heroku deployment.

```bash
# Create app
heroku create your-app-name

# Add PostgreSQL
heroku addons:create heroku-postgresql:essential-0

# Set config vars
heroku config:set SECRET_KEY=your-production-secret
heroku config:set DEBUG=False
heroku config:set ALLOWED_HOSTS=your-app.herokuapp.com
heroku config:set GEMINI_API_KEY=your-key
heroku config:set OPENWEATHERMAP_API_KEY=your-key
heroku config:set FRONTEND_URL=https://your-frontend.netlify.app

# Deploy
git push heroku main

# Seed demo data on Heroku
heroku run python manage.py seed_demo
```

**Twilio webhook URL:** `https://your-app.herokuapp.com/api/v1/webhook/sms/`

Set this in Twilio Console → Phone Numbers → your number → Messaging → "A message comes in" → HTTP POST.

## Documentation

Detailed guides for each integration in `API_DOCS/`:

- **[Frontend Guide](API_DOCS/FRONTEND_GUIDE.md)** — Next.js integration, auth flow, all endpoints with request/response examples, dashboard page suggestions
- **[Twilio Guide](API_DOCS/TWILIO_GUIDE.md)** — SMS webhook setup, ngrok testing, phone registration
- **[Agent Architecture](API_DOCS/AGENT_ARCHITECTURE.md)** — Multi-agent pipeline, tool execution, data flow, trace structure
