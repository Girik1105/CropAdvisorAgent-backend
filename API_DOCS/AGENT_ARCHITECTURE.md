# Agent Architecture

## Overview

CropAdvisor uses a **multi-agent pipeline** where three specialized Gemini agents work in sequence. Each "agent" is a Gemini 1.5 Flash API call with a different system prompt and role. The pipeline follows a **sense → reason → act → notify** loop.

```
User Message
    ↓
┌─────────────────────────────────────────────────┐
│  CropAdvisorEngine.run(field_id, message, sid)  │
│                                                 │
│  1. Field Agent (sense)                         │
│     ├─ calls get_weather(lat, lng)              │
│     ├─ calls get_crop_health(field_id)          │
│     ├─ calls get_soil_profile(field_id)         │
│     └─ outputs: field context summary           │
│                                                 │
│  2. Orchestrator Agent (reason)                 │
│     ├─ receives: field context + user message   │
│     └─ outputs: action plan with reasoning      │
│                                                 │
│  3. Recommender Agent (act)                     │
│     ├─ receives: plan + field context + message  │
│     └─ outputs: costed recommendation           │
│                                                 │
│  4. Save & Format (notify)                      │
│     ├─ saves ActionRecommendation to DB         │
│     └─ formats farmer-friendly response text    │
└─────────────────────────────────────────────────┘
    ↓
Response: { session_id, response, recommendation, total_duration_ms }
```

---

## The Three Agents

### 1. Field Agent (`_field_agent`)

**Role:** Autonomous data gatherer. Uses Gemini function calling to invoke all three tools without being told which ones to call.

**System Prompt:** `FIELD_AGENT_PROMPT` (in `agent/prompts.py`)
- Receives field metadata (name, crop type, coordinates, field ID)
- Instructed to call ALL three tools automatically
- After tool calls, produces a JSON summary of field conditions

**Gemini interaction:**
1. Sends prompt with field details → Gemini decides which tools to call
2. Gemini returns `function_call` parts → engine executes each tool
3. Engine sends tool results back → Gemini produces field context JSON

**Output shape:**
```json
{
  "weather_summary": "105°F, 12% humidity, no rain in 7-day forecast",
  "crop_health_status": "NDVI 0.42 — moderate stress, declining trend",
  "soil_conditions": "Sandy loam, pH 7.8, low water-holding capacity",
  "urgent_concerns": ["Heat stress", "No precipitation forecast"],
  "data_quality": "All three data sources returned successfully"
}
```

### 2. Orchestrator Agent (`_orchestrator_agent`)

**Role:** Strategic analyzer. Decides what action is needed and why.

**System Prompt:** `ORCHESTRATOR_PROMPT` (in `agent/prompts.py`)
- Receives the field context from Agent 1 + the farmer's original message
- Analyzes through: immediate threats, opportunity windows, resource optimization, risk assessment
- Considers crop-specific factors (cotton, alfalfa, citrus)

**No tool calling** — this is a pure reasoning step (single `generate_content` call).

**Output shape:**
```json
{
  "primary_concern": "Drought stress with high heat",
  "recommended_action": "irrigate",
  "urgency_level": "within_24h",
  "reasoning": "NDVI declining + 105°F + no rain forecast = immediate water need",
  "data_supporting": ["NDVI 0.42", "temp 105°F", "0% precipitation 7-day"],
  "alternative_considered": "Fertigation — rejected, stress too high for nutrient uptake"
}
```

### 3. Recommender Agent (`_recommender_agent`)

**Role:** Generates the final, specific recommendation with cost estimates and risk quantification.

**System Prompt:** `RECOMMENDER_PROMPT` (in `agent/prompts.py`)
- Receives the orchestrator's plan + field context + original message
- Has cost estimation guidelines built into the prompt (irrigation $25-45/acre, etc.)
- Has Arizona agricultural context (desert soils, monsoon patterns, heat stress thresholds)

**No tool calling** — pure reasoning step.

**Output shape:**
```json
{
  "action_type": "irrigate",
  "urgency": "within_24h",
  "description": "Apply 2.5 inches of water to cotton field",
  "estimated_cost": 45.0,
  "cost_breakdown": "2 acre-inches @ $22.50/inch = $45",
  "risk_if_delayed": "12% yield loss if delayed beyond 3 days",
  "timing_rationale": "Apply before 10am to minimize evaporation loss",
  "implementation_steps": ["Check drip system pressure", "Run for 6 hours", "Verify soil moisture after"]
}
```

---

## Tool Execution

The engine has three tools available via Gemini function calling. These are defined as Gemini `Tool` schemas in `engine.__init__()`.

### Tool Schemas (passed to Gemini)

```
get_weather(lat: number, lng: number)
get_crop_health(field_id: string)
get_soil_profile(field_id: string)
```

### How Tools Are Called

The Field Agent sends a prompt to Gemini. Gemini responds with `function_call` parts indicating which tools to invoke and with what arguments. The engine then:

1. Extracts `function_call.name` and `function_call.args` from Gemini's response
2. Calls the corresponding Python function in `tools/services.py` directly (no HTTP)
3. Saves the tool call + result as an `AgentMessage` with role `tool_call`
4. Sends the result back to Gemini for the agent to use

### Tool Functions (`tools/services.py`)

| Function | Data Source | DB Storage |
|----------|------------|------------|
| `get_weather(lat, lng, field, session)` | OpenWeatherMap API (static fallback) | Saves **WeatherSnapshot** per call |
| `get_crop_health(field_id, field)` | **CropHealthRecord** from DB | Reads latest record; creates default if none |
| `get_soil_profile(field_id, field)` | **SoilProfile** from DB | Reads profile; creates default if none |

When called from the engine, the `field` and `session` objects are passed so data is persisted. When called from the tool API endpoints (`/api/v1/tools/`), no field is passed so data is returned without saving.

---

## Data Flow Through Models

```
Field (registered crop field)
  │
  ├─→ WeatherSnapshot (one per agent run — historical weather data)
  │     temp_f, humidity_pct, wind_mph, conditions, uv_index
  │     precipitation_forecast (JSON array)
  │     linked to session that triggered it
  │
  ├─→ CropHealthRecord (NDVI readings over time)
  │     ndvi_score, stress_level, vegetation_trend
  │     vegetation_fraction, last_satellite_date
  │
  ├─→ SoilProfile (one-to-one — soil characteristics)
  │     soil_type, ph, organic_matter_pct
  │     drainage_class, water_holding_capacity
  │
  └─→ AgentSession (one per user+field+channel combo)
        │
        ├─→ AgentMessage (ordered by created_at)
        │     role: user    ← farmer's input
        │     role: agent   ← field context / orchestrator plan / recommendation / final text
        │
        └─→ ActionRecommendation
              action_type, urgency, description
              estimated_cost, cost_breakdown
              risk_if_delayed, timing_rationale
              implementation_steps (JSON array)
```

### What Gets Saved Per Agent Run

| Model | When Created | Data Source |
|-------|-------------|-------------|
| WeatherSnapshot | Every run | OpenWeatherMap API or static fallback |
| CropHealthRecord | First run only (unless updated) | Default demo values |
| SoilProfile | First run only (unless updated) | Default demo values |
| AgentMessage (x4-5) | Every run | User input + Gemini outputs |
| ActionRecommendation | Every run | Gemini recommender agent |

### Message Roles (in execution order)

| Role | Source | Content |
|------|--------|---------|
| `user` | Farmer | Original message text |
| `agent` | Engine | Field context JSON (weather + NDVI + soil gathered) |
| `agent` | Gemini | Orchestrator plan JSON (primary concern, reasoning) |
| `agent` | Gemini | Recommender output JSON (action, cost, steps) |
| `agent` | Engine | Final farmer-friendly text response |

---

## Engine Return Format

`CropAdvisorEngine.run()` returns:

```json
{
  "session_id": "uuid-string",
  "response": "Your cotton is showing early drought stress. Irrigate within 24 hours. Estimated cost: $70. Delaying risks 15% yield loss.",
  "recommendation": {
    "action_type": "irrigate",
    "urgency": "immediate",
    "description": "Apply 2.5 inches of water to cotton field",
    "estimated_cost": 70.0,
    "risk_if_delayed": "15% yield loss if delayed beyond 48 hours"
  },
  "total_duration_ms": 20467
}
```

**What's also saved to DB** (not in the return, but queryable via endpoints):

| Saved To | Queryable At |
|----------|-------------|
| WeatherSnapshot | `GET /fields/<id>/weather/` |
| CropHealthRecord (if new) | `GET /fields/<id>/crop-health/` |
| SoilProfile (if new) | `GET /fields/<id>/soil/` |
| ActionRecommendation (with cost_breakdown, timing_rationale, implementation_steps) | `GET /agent/trace/<session_id>/` → `recommendations[]` |
```

This is returned directly by both:
- `POST /api/v1/agent/message/` (dashboard) — as JSON
- `POST /api/v1/webhook/sms/` (Twilio) — `response` field wrapped in TwiML

---

## Two Entry Points, Same Engine

```
Dashboard (Next.js)                    Twilio SMS
    │                                      │
    ▼                                      ▼
POST /api/v1/agent/message/      POST /api/v1/webhook/sms/
    │  JWT auth                        │  No auth (AllowAny)
    │  JSON body                       │  Form data (From, Body)
    │  field_id from request           │  field looked up by phone
    │                                  │
    └──────────┬───────────────────────┘
               ▼
     AgentSession created
     (channel: dashboard or sms)
               │
               ▼
     CropAdvisorEngine.run()
     (identical pipeline either way)
               │
               ▼
     ┌─────────┴──────────┐
     ▼                    ▼
  JSON response       TwiML response
  (to frontend)       (to Twilio → farmer)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `agent/engine.py` | `CropAdvisorEngine` class — orchestrates the 3-agent pipeline |
| `agent/prompts.py` | System prompts for Field Agent, Orchestrator, Recommender |
| `agent/models.py` | Field, WeatherSnapshot, CropHealthRecord, SoilProfile, AgentSession, AgentMessage, ActionRecommendation |
| `agent/views.py` | API views (message, trace, fields, sessions, weather/crop/soil history) |
| `agent/serializers.py` | DRF serializers for all models |
| `tools/services.py` | Tool functions — read/write weather, crop health, soil to DB |
| `webhooks/views.py` | Twilio SMS webhook handler |
| `agent/management/commands/seed_demo.py` | Seed demo data for testing |

---

## Timing

A typical run takes ~10-25 seconds:
- Field Agent: ~1-2s (data gathering from tools/services.py + DB writes)
- Orchestrator: ~5-10s (Gemini API call)
- Recommender: ~5-10s (Gemini API call)

---

## Seed Data

Run `python manage.py seed_demo` to populate the DB with:
- 1 demo user (`demo_farmer` / `demo1234!`)
- 3 fields with different crops (cotton, citrus, alfalfa)
- Soil profiles, crop health records, and weather snapshots per field

Add `--run-agent` to also run the Gemini pipeline on the first field.
Add `--reset` to wipe everything and start fresh.
