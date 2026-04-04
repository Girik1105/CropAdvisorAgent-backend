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

| Function | Data Source | Notes |
|----------|------------|-------|
| `get_weather(lat, lng)` | OpenWeatherMap API | Falls back to static data if no API key |
| `get_crop_health(field_id)` | Static JSON | Hackathon — returns hardcoded NDVI data |
| `get_soil_profile(field_id)` | Static JSON | Hackathon — returns hardcoded USDA soil data |

These same functions are also exposed as API endpoints at `/api/v1/tools/` for frontend debugging.

---

## Data Flow Through Models

```
Field (registered crop field)
  │
  └─→ AgentSession (one per user+field+channel combo)
        │
        ├─→ AgentMessage (ordered by created_at)
        │     role: user           ← farmer's input
        │     role: tool_call      ← get_weather, get_crop_health, get_soil_profile
        │     role: field_agent    ← Agent 1 output
        │     role: orchestrator   ← Agent 2 output
        │     role: recommender    ← Agent 3 output
        │     role: final_response ← formatted response text
        │
        └─→ ActionRecommendation
              action_type: irrigate/fertilize/pest_alert/harvest/no_action
              urgency: immediate/within_24h/within_3d/monitor
              estimated_cost: decimal
              risk_if_delayed: text
```

### Message Roles (in execution order)

| Role | Source | Content |
|------|--------|---------|
| `user` | Farmer | Original message text |
| `tool_call` | Engine | Tool name, input args, output data, duration_ms |
| `field_agent` | Gemini | JSON field context summary |
| `orchestrator` | Gemini | JSON action plan |
| `recommender` | Gemini | JSON recommendation with costs |
| `final_response` | Engine | Formatted farmer-friendly text |

---

## Engine Return Format

`CropAdvisorEngine.run()` returns:

```json
{
  "session_id": "uuid-string",
  "response": "Your cotton is showing early drought stress. Irrigate within 24 hours. Estimated cost: $45. Delaying 3+ days risks 12% yield loss.",
  "recommendation": {
    "action_type": "irrigate",
    "urgency": "within_24h",
    "description": "Apply 2.5 inches of water to cotton field",
    "estimated_cost": 45.0,
    "risk_if_delayed": "12% yield loss if delayed beyond 3 days"
  },
  "total_duration_ms": 3400
}
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
| `agent/models.py` | Field, AgentSession, AgentMessage, ActionRecommendation |
| `agent/views.py` | API views (message, trace, fields, sessions) |
| `tools/services.py` | Tool functions (weather, crop health, soil) |
| `webhooks/views.py` | Twilio SMS webhook handler |

---

## Timing

A typical run takes ~3-5 seconds:
- Field Agent: ~1-2s (Gemini call + 3 tool executions)
- Orchestrator: ~0.5-1s (single Gemini call)
- Recommender: ~0.5-1s (single Gemini call)

Each step's duration is saved in `AgentMessage.duration_ms` for the trace view.
