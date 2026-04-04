# CropAdvisor Backend

Django + DRF backend for the CropAdvisor autonomous AI agent built for Innovation Hacks 2.0. A farmer texts a phone number and receives a specific, costed action plan for their field — no app, no dashboard, no smartphone required.

**Demo:** Cotton farmer near Casa Grande, AZ texts "How's my field looking?" → Agent gathers weather, NDVI, and soil data → Responds: "Your cotton is showing early drought stress. Irrigate within 24 hours. Estimated water cost: $45. Delaying 3+ days risks 12% yield loss."

## Setup

### 1. Create and activate virtual environment

```bash
# From the parent directory (CropAdvisor/)
python3 -m venv venv
source venv/bin/activate
```

Or if the venv already exists:

```bash
source ../venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

For the full agent engine (Gemini/Vertex AI), also install:

```bash
pip install google-cloud-aiplatform>=1.38.0
```

### 3. Set up environment variables

Copy the `.env` file and fill in your API keys:

```bash
cp .env.example .env   # or edit .env directly
```

**Required variables:**

| Variable | Purpose | Where to get it |
|----------|---------|-----------------|
| `SECRET_KEY` | Django secret key | Auto-generated, change for production |
| `DEBUG` | Debug mode | `True` for development |
| `GCP_PROJECT_ID` | Google Cloud project | [GCP Console](https://console.cloud.google.com/) |
| `GCP_REGION` | Vertex AI region | Default: `us-central1` |
| `GEMINI_API_KEY` | Gemini API key | [Google AI Studio](https://aistudio.google.com/) |
| `OPENWEATHERMAP_API_KEY` | Weather data | [OpenWeatherMap](https://openweathermap.org/api) |
| `TWILIO_ACCOUNT_SID` | Twilio account | [Twilio Console](https://console.twilio.com/) |
| `TWILIO_AUTH_TOKEN` | Twilio auth | Twilio Console |
| `TWILIO_PHONE_NUMBER` | SMS phone number | Twilio Console |
| `ELEVENLABS_API_KEY` | Voice TTS | [ElevenLabs](https://elevenlabs.io/) (MLH promo code) |
| `FRONTEND_URL` | CORS origin | Default: `http://localhost:3000` |

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Create a superuser (optional, for admin panel)

```bash
python manage.py createsuperuser
```

### 6. Start the development server

```bash
python manage.py runserver
```

The API is now available at `http://127.0.0.1:8000/api/v1/`.

## Project Structure

```
├── config/                  # Django project configuration
│   ├── settings.py          # Settings, env vars, JWT config, CORS
│   ├── urls.py              # Root URL router
│   └── wsgi.py
├── accounts/                # Authentication app
│   ├── serializers.py       # SignupSerializer
│   ├── views.py             # SignupView (JWT token generation)
│   └── urls.py              # /auth/signup/, /auth/login/, /auth/token/refresh/
├── agent/                   # Core agent app
│   ├── models.py            # Field, AgentSession, AgentMessage, ActionRecommendation
│   ├── engine.py            # CropAdvisorEngine — 3-agent Gemini pipeline
│   ├── prompts.py           # System prompts for each agent
│   ├── serializers.py       # DRF serializers for all models
│   ├── views.py             # Agent message, trace, field, session views
│   ├── urls.py              # /agent/message/, /agent/trace/
│   └── urls_fields.py       # /fields/, /fields/<id>/sessions/
├── tools/                   # Data tool app
│   ├── services.py          # get_weather(), get_crop_health(), get_soil_profile()
│   ├── views.py             # Tool API endpoints
│   └── urls.py              # /tools/weather/, /tools/crop-health/, /tools/soil/
├── webhooks/                # Twilio integration
│   ├── views.py             # SMS webhook handler (TwiML response)
│   └── urls.py              # /webhook/sms/
├── API_DOCS/                # Documentation for team members
│   ├── FRONTEND_GUIDE.md    # Next.js integration guide
│   ├── TWILIO_GUIDE.md      # Twilio SMS setup guide
│   └── AGENT_ARCHITECTURE.md # How the agent engine works
├── .env                     # Environment variables (not committed)
├── .gitignore
├── requirements.txt
└── manage.py
```

## Data Models

All models are in `agent/models.py` with UUID primary keys.

### Field
A registered crop field linked to a user.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| owner | FK → User | Field owner (Django User) |
| name | string | e.g. "North 40" |
| crop_type | string | cotton, alfalfa, citrus |
| lat / lng | float | Field centroid coordinates |
| area_acres | float | Field size |
| soil_type | string | USDA classification |
| owner_phone | string | Owner's phone (E.164) — used for Twilio SMS lookup |

### AgentSession
A conversation session between a user and the agent.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user | FK → User | Session owner |
| field | FK → Field | Associated field |
| channel | enum | `sms` or `dashboard` |
| phone_number | string | Populated for SMS sessions |
| created_at / updated_at | datetime | Timestamps |

### AgentMessage
Individual messages in a session, including tool calls and agent reasoning.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| session | FK → AgentSession | Parent session |
| role | enum | `user`, `tool_call`, `field_agent`, `orchestrator`, `recommender`, `final_response` |
| content | text | Message text or JSON output |
| tool_name | string | Tool called (if role is tool_call) |
| tool_input / tool_output | JSON | Tool arguments and results |
| duration_ms | int | Execution time for this step |

### ActionRecommendation
Structured recommendation saved from the agent pipeline.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| session | FK → AgentSession | Parent session |
| field | FK → Field | Target field |
| action_type | enum | `irrigate`, `fertilize`, `pest_alert`, `harvest`, `no_action` |
| urgency | enum | `immediate`, `within_24h`, `within_3d`, `monitor` |
| description | text | Farmer-friendly explanation |
| estimated_cost | decimal | Dollar cost estimate |
| risk_if_delayed | text | Consequence of inaction |

## API Endpoints

All endpoints are prefixed with `/api/v1/`.

### Authentication (no auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup/` | Register user, returns JWT tokens |
| POST | `/auth/login/` | Login, returns JWT tokens |
| POST | `/auth/token/refresh/` | Refresh access token |

### Agent (JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agent/message/` | Send message to agent, get recommendation |
| GET | `/agent/trace/<session_id>/` | Full reasoning trace for a session |

### Fields (JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/fields/` | List user's fields |
| POST | `/fields/` | Create a new field |
| GET | `/fields/<field_id>/sessions/` | List sessions for a field |

### Tools (no auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tools/weather/?lat=&lng=` | Weather + 7-day forecast |
| GET | `/tools/crop-health/?field_id=` | NDVI vegetation health |
| GET | `/tools/soil/?field_id=` | USDA soil profile |

### Webhook (no auth required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhook/sms/` | Twilio inbound SMS webhook |

## Agent Engine

The backend runs a 3-agent Gemini pipeline for every message:

```
User Message → Field Agent (gathers data) → Orchestrator (plans action) → Recommender (costs it) → Response
```

1. **Field Agent** — Autonomously calls 3 tools (weather, NDVI, soil) via Gemini function calling
2. **Orchestrator** — Analyzes data + farmer's message, creates action plan
3. **Recommender** — Generates specific recommendation with cost estimate and risk

Both the dashboard (`POST /agent/message/`) and Twilio SMS (`POST /webhook/sms/`) run the same engine. See `API_DOCS/AGENT_ARCHITECTURE.md` for full details.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 5.2 + Django REST Framework |
| Auth | SimpleJWT (access + refresh tokens) |
| Agent | Gemini 1.5 Flash via Vertex AI |
| Weather | OpenWeatherMap API |
| NDVI | Static data (hackathon) |
| Soil | Static data (hackathon) |
| SMS | Twilio |
| Voice | ElevenLabs (not yet implemented) |
| Database | SQLite (dev) |

## Documentation

Detailed guides for each integration are in `API_DOCS/`:

- **[Frontend Guide](API_DOCS/FRONTEND_GUIDE.md)** — Next.js integration, auth flow, all endpoints with examples
- **[Twilio Guide](API_DOCS/TWILIO_GUIDE.md)** — SMS webhook setup, ngrok testing, phone registration
- **[Agent Architecture](API_DOCS/AGENT_ARCHITECTURE.md)** — Multi-agent pipeline, data flow, tool execution
