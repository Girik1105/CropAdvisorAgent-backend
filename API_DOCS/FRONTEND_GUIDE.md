# Frontend Integration Guide (Next.js)

## Overview

The backend exposes a REST API at `http://localhost:8000/api/v1/`. All endpoints return JSON. Most endpoints require JWT authentication. CORS is configured to allow `http://localhost:3000`.

**Quick start:** Run `python manage.py seed_demo` to populate the DB with a demo user and 3 fields with full data. Login: `demo_farmer` / `demo1234!`

## Base URL

```
http://localhost:8000/api/v1/
```

---

## Authentication

The backend uses JWT (access + refresh tokens) via SimpleJWT.

### Sign Up

```
POST /api/v1/auth/signup/
Content-Type: application/json

{
  "username": "farmer1",
  "email": "farmer@example.com",
  "password": "securepass123"
}
```

**Response (201):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Log In

```
POST /api/v1/auth/login/
Content-Type: application/json

{
  "username": "farmer1",
  "password": "securepass123"
}
```

**Response (200):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Refresh Token

```
POST /api/v1/auth/token/refresh/
Content-Type: application/json

{
  "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Token Lifetimes
- **Access token:** 30 minutes
- **Refresh token:** 7 days

### Sending Authenticated Requests

Include the access token in the `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Next.js Token Storage

Store tokens in `localStorage` or a cookie. Example helper:

```typescript
// lib/api.ts
const API_BASE = "http://localhost:8000/api/v1";

export async function apiFetch(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  });

  // Auto-refresh on 401
  if (res.status === 401) {
    const refreshed = await refreshToken();
    if (refreshed) return apiFetch(path, options); // retry
    // redirect to login
  }

  return res;
}

async function refreshToken(): Promise<boolean> {
  const refresh = localStorage.getItem("refresh_token");
  if (!refresh) return false;

  const res = await fetch(`${API_BASE}/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });

  if (res.ok) {
    const data = await res.json();
    localStorage.setItem("access_token", data.access);
    return true;
  }
  return false;
}
```

---

## Fields

### List Fields

```
GET /api/v1/fields/
Authorization: Bearer <token>
```

**Response (200):**
```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "North 40",
    "crop_type": "cotton",
    "lat": 32.87,
    "lng": -111.75,
    "area_acres": 40.0,
    "soil_type": "sandy loam",
    "owner_phone": "+16025551234"
  }
]
```

### Create Field

```
POST /api/v1/fields/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "North 40",
  "crop_type": "cotton",
  "lat": 32.87,
  "lng": -111.75,
  "area_acres": 40.0,
  "soil_type": "sandy loam",
  "owner_phone": "+16025551234"
}
```

**Response (201):** Same shape as list item above.

---

## Field Data (Weather, Crop Health, Soil)

Each field has associated environmental data stored in the database. These are populated automatically when the agent runs, or can be seeded with `python manage.py seed_demo`.

### Weather History

Returns all weather snapshots for a field, most recent first. A new snapshot is created each time the agent runs.

```
GET /api/v1/fields/<field_id>/weather/
Authorization: Bearer <token>
```

**Response (200):**
```json
[
  {
    "id": "w1x2y3z4-...",
    "field": "a1b2c3d4-...",
    "temp_f": 105,
    "temp_c": 40.6,
    "humidity_pct": 12,
    "wind_mph": 8,
    "conditions": "clear sky",
    "uv_index": 11,
    "precipitation_forecast": [
      {"date": "2026-04-04", "precip_in": 0.0, "prob_pct": 0},
      {"date": "2026-04-05", "precip_in": 0.0, "prob_pct": 5},
      {"date": "2026-04-06", "precip_in": 0.0, "prob_pct": 0}
    ],
    "created_at": "2026-04-04T12:00:00Z"
  }
]
```

**Dashboard usage:** Show a weather card for the latest entry. Use the list to build a temperature/humidity chart over time.

### Crop Health History (NDVI)

Returns NDVI vegetation health records for a field, most recent first. A record is created when the agent first runs on a field (with default demo values), and can be updated via admin or future satellite integrations.

```
GET /api/v1/fields/<field_id>/crop-health/
Authorization: Bearer <token>
```

**Response (200):**
```json
[
  {
    "id": "c1d2e3f4-...",
    "field": "a1b2c3d4-...",
    "ndvi_score": 0.42,
    "stress_level": "moderate",
    "vegetation_trend": "declining",
    "vegetation_fraction": 0.58,
    "last_satellite_date": "2026-04-03T14:30:00Z",
    "created_at": "2026-04-04T12:00:00Z"
  }
]
```

**NDVI scale for UI color coding:**

| NDVI Range | Stress Level | Suggested Color |
|------------|-------------|-----------------|
| 0.0 - 0.2 | Severe | Red |
| 0.2 - 0.4 | High | Orange |
| 0.4 - 0.6 | Moderate | Yellow |
| 0.6 - 0.8 | Low (healthy) | Light Green |
| 0.8 - 1.0 | None (peak) | Green |

**Dashboard usage:** Show NDVI as a gauge/meter with color. Use history to build a vegetation health trend chart.

### Soil Profile

Returns the soil profile for a field. One profile per field (created on first agent run or via seed data).

```
GET /api/v1/fields/<field_id>/soil/
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "id": "s1t2u3v4-...",
  "field": "a1b2c3d4-...",
  "soil_type": "Casa Grande sandy loam",
  "ph": 7.8,
  "organic_matter_pct": 1.2,
  "drainage_class": "well-drained",
  "water_holding_capacity": "low",
  "available_water_in_per_ft": 1.1,
  "updated_at": "2026-04-04T12:00:00Z"
}
```

**Response (404):** `{"error": "No soil profile for this field"}` — field exists but no soil data yet.

**Dashboard usage:** Display as a static info card with soil properties. Useful context alongside recommendations.

---

## Agent Interaction

### Send a Message

This is the main endpoint. It runs the full 3-agent Gemini pipeline and returns a recommendation. It also automatically:
- Saves a new **WeatherSnapshot** for the field
- Reads/creates **CropHealthRecord** and **SoilProfile** if they don't exist
- Saves a structured **ActionRecommendation** with cost breakdown

```
POST /api/v1/agent/message/
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "How's my field looking?",
  "field_id": "a1b2c3d4-..."       // optional — uses first field if omitted
}
```

**Response (200):**
```json
{
  "session_id": "e5f6g7h8-...",
  "response": "Your cotton is showing early drought stress. Irrigate within 24 hours. Estimated water cost: $70. Delaying risks 15% yield loss.",
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

**Note:** This request takes 10-25 seconds (3 sequential Gemini API calls). Show a loading state in the UI.

**Possible `action_type` values:** `irrigate`, `fertilize`, `pest_alert`, `harvest`, `no_action`

**Possible `urgency` values:** `immediate`, `within_24h`, `within_3d`, `monitor`

**After this call completes**, the field data endpoints will have fresh data:
- `/fields/<id>/weather/` — new snapshot added
- `/fields/<id>/crop-health/` — record exists (or created)
- `/fields/<id>/soil/` — profile exists (or created)

### Get Reasoning Trace

Shows the full agent reasoning chain for a session — every tool call, agent output, and timing. Use this to build the "agent thinking" visualization on the dashboard.

```
GET /api/v1/agent/trace/<session_id>/
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "session": {
    "id": "e5f6g7h8-...",
    "phone_number": "",
    "field": "a1b2c3d4-...",
    "field_name": "North 40",
    "channel": "dashboard",
    "created_at": "2026-04-04T12:00:00Z",
    "updated_at": "2026-04-04T12:00:20Z"
  },
  "messages": [
    {
      "id": "...",
      "role": "user",
      "content": "How's my field looking?",
      "tool_name": null,
      "tool_input": null,
      "tool_output": null,
      "duration_ms": null,
      "created_at": "2026-04-04T12:00:00Z"
    },
    {
      "id": "...",
      "role": "agent",
      "content": "{\"field_name\": \"North 40\", \"crop_type\": \"cotton\", \"weather\": {...}, \"crop_health\": {...}, \"soil\": {...}}",
      "tool_name": null,
      "tool_input": null,
      "tool_output": null,
      "duration_ms": null,
      "created_at": "2026-04-04T12:00:01Z"
    },
    {
      "id": "...",
      "role": "agent",
      "content": "{\"primary_concern\": \"drought stress\", \"recommended_action\": \"irrigate\", ...}",
      "tool_name": null,
      "tool_input": null,
      "tool_output": null,
      "duration_ms": null,
      "created_at": "2026-04-04T12:00:10Z"
    },
    {
      "id": "...",
      "role": "agent",
      "content": "{\"action_type\": \"irrigate\", \"estimated_cost\": 70, ...}",
      "tool_name": null,
      "tool_input": null,
      "tool_output": null,
      "duration_ms": null,
      "created_at": "2026-04-04T12:00:18Z"
    },
    {
      "id": "...",
      "role": "agent",
      "content": "Your 'North 40' cotton field is under severe drought stress...",
      "tool_name": null,
      "tool_input": null,
      "tool_output": null,
      "duration_ms": null,
      "created_at": "2026-04-04T12:00:20Z"
    }
  ],
  "recommendations": [
    {
      "id": "...",
      "action_type": "irrigate",
      "urgency": "immediate",
      "description": "Apply 2.5 inches of water to cotton field",
      "estimated_cost": "70.00",
      "cost_breakdown": "40 acres x $1.75/acre-inch x 1 inch = $70",
      "risk_if_delayed": "15% yield loss if delayed beyond 48 hours",
      "timing_rationale": "Apply before 10am to minimize evaporation",
      "implementation_steps": [
        "Check drip irrigation system pressure",
        "Run irrigation for 6 hours",
        "Verify soil moisture 12 hours after"
      ],
      "created_at": "2026-04-04T12:00:20Z"
    }
  ]
}
```

**Agent message roles in the trace:**

| Order | Role | What It Contains | How to Display |
|-------|------|-----------------|----------------|
| 1 | `user` | Farmer's original message | Chat bubble (left) |
| 2 | `agent` | Field context JSON (weather + NDVI + soil) | Collapsible "Data Gathered" card |
| 3 | `agent` | Orchestrator plan JSON (primary concern, reasoning) | Collapsible "Analysis" card |
| 4 | `agent` | Recommender output JSON (action, cost, steps) | Collapsible "Recommendation Details" card |
| 5 | `agent` | Final farmer-friendly text response | Chat bubble (right) |

**Tip:** Parse the `content` field as JSON for messages 2-4 to render structured data. Message 5 is plain text.

---

## Sessions

### List Sessions for a Field

```
GET /api/v1/fields/<field_id>/sessions/
Authorization: Bearer <token>
```

**Response (200):**
```json
[
  {
    "id": "e5f6g7h8-...",
    "phone_number": "+16025551234",
    "field": "a1b2c3d4-...",
    "field_name": "North 40",
    "channel": "sms",
    "created_at": "2026-04-04T10:00:00Z",
    "updated_at": "2026-04-04T10:00:05Z"
  },
  {
    "id": "f6g7h8i9-...",
    "phone_number": "",
    "field": "a1b2c3d4-...",
    "field_name": "North 40",
    "channel": "dashboard",
    "created_at": "2026-04-04T12:00:00Z",
    "updated_at": "2026-04-04T12:00:20Z"
  }
]
```

Sessions are returned most recent first. Both SMS and dashboard sessions appear here.

---

## Tool Endpoints (Raw Data / Debug)

These are the raw data endpoints the agent calls internally. No auth required. Useful for quick debugging or showing live tool data.

**Note:** These do NOT save data to the database. Use the field data endpoints above (`/fields/<id>/weather/`, etc.) for persisted data.

### Weather (live)

```
GET /api/v1/tools/weather/?lat=32.87&lng=-111.75
```

### Crop Health (static default)

```
GET /api/v1/tools/crop-health/?field_id=a1b2c3d4-...
```

### Soil Profile (static default)

```
GET /api/v1/tools/soil/?field_id=a1b2c3d4-...
```

---

## Complete Endpoint Reference

### No Auth Required

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup/` | Register, get JWT tokens |
| POST | `/auth/login/` | Login, get JWT tokens |
| POST | `/auth/token/refresh/` | Refresh access token |
| GET | `/tools/weather/` | Live weather (debug) |
| GET | `/tools/crop-health/` | Static NDVI (debug) |
| GET | `/tools/soil/` | Static soil (debug) |
| POST | `/webhook/sms/` | Twilio SMS webhook |

### JWT Required

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/fields/` | List user's fields |
| POST | `/fields/` | Create a field |
| GET | `/fields/<id>/sessions/` | Sessions for a field |
| GET | `/fields/<id>/weather/` | Weather snapshot history |
| GET | `/fields/<id>/crop-health/` | NDVI record history |
| GET | `/fields/<id>/soil/` | Soil profile |
| POST | `/agent/message/` | Send message, run agent |
| GET | `/agent/trace/<session_id>/` | Full reasoning trace |

---

## Dashboard Page Suggestions

Here's how to map these endpoints to dashboard pages:

### 1. Field Overview Page (`/dashboard/fields/<id>`)
Fetch in parallel on page load:
```
GET /fields/<id>/weather/       → latest weather card
GET /fields/<id>/crop-health/   → NDVI gauge + trend chart
GET /fields/<id>/soil/          → soil info card
GET /fields/<id>/sessions/      → recent session list
```

### 2. Agent Chat Page (`/dashboard/fields/<id>/chat`)
```
POST /agent/message/            → send message, show loading (10-25s)
                                → display response + recommendation card
GET /agent/trace/<session_id>/  → show reasoning trace (expandable)
```

### 3. Session History Page (`/dashboard/fields/<id>/sessions/<session_id>`)
```
GET /agent/trace/<session_id>/  → full trace with all messages
```

### 4. Field List / Home (`/dashboard`)
```
GET /fields/                    → list all fields with cards
```

---

## Error Handling

| Status | Meaning | When |
|--------|---------|------|
| 200 | Success | Normal response |
| 201 | Created | Signup, field creation |
| 400 | Bad Request | Missing required fields, no fields registered |
| 401 | Unauthorized | Missing/expired JWT token |
| 404 | Not Found | Invalid field_id, session_id, or no soil profile |
| 500 | Server Error | Agent engine failure (Gemini API down, etc.) |

**401 response shape:**
```json
{
  "detail": "Given token not valid for any token type",
  "code": "token_not_valid",
  "messages": [...]
}
```

**400/404/500 response shape:**
```json
{
  "error": "Field not found"
}
```

---

## CORS

The backend allows requests from:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

Credentials are allowed (`CORS_ALLOW_CREDENTIALS = True`).

If you change the frontend port, update `FRONTEND_URL` in the backend `.env` file.

---

## Demo Data

Run this to populate the database for frontend development:

```bash
python manage.py seed_demo
```

This creates:
- **User:** `demo_farmer` / `demo1234!`
- **3 Fields:** North 40 (cotton), South Orchard (citrus), West Pasture (alfalfa)
- **3 Soil Profiles:** Different soil types per field
- **3 Crop Health Records:** Different NDVI scores per field
- **3 Weather Snapshots:** Different conditions per field

To also run the agent pipeline and generate a real recommendation:

```bash
python manage.py seed_demo --run-agent
```

To reset everything and start fresh:

```bash
python manage.py seed_demo --reset
```
