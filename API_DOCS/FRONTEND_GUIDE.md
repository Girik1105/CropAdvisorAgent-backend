# Frontend Integration Guide (Next.js)

## Overview

The backend exposes a REST API at `http://localhost:8000/api/v1/`. All endpoints return JSON. Most endpoints require JWT authentication. CORS is configured to allow `http://localhost:3000`.

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

## Agent Interaction

### Send a Message

This is the main endpoint. It runs the full 3-agent Gemini pipeline and returns a recommendation.

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
  "response": "Your cotton is showing early drought stress. Irrigate within 24 hours. Estimated water cost: $45. Delaying 3+ days risks 12% yield loss.",
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

**Note:** This request may take 3-10 seconds (3 sequential Gemini API calls). Show a loading state in the UI.

**Possible `action_type` values:** `irrigate`, `fertilize`, `pest_alert`, `harvest`, `no_action`

**Possible `urgency` values:** `immediate`, `within_24h`, `within_3d`, `monitor`

### Get Reasoning Trace

Shows the full agent reasoning chain for a session — every tool call, agent output, and timing.

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
    "updated_at": "2026-04-04T12:00:03Z"
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
      "role": "tool_call",
      "content": "Called get_weather with {'lat': 32.87, 'lng': -111.75}",
      "tool_name": "get_weather",
      "tool_input": {"lat": 32.87, "lng": -111.75},
      "tool_output": {"temp_f": 105, "humidity_pct": 12, "conditions": "clear sky"},
      "duration_ms": 340,
      "created_at": "2026-04-04T12:00:00Z"
    },
    {
      "id": "...",
      "role": "field_agent",
      "content": "{\"weather_summary\": \"...\", \"crop_health_status\": \"...\"}",
      "tool_name": null,
      "tool_input": null,
      "tool_output": null,
      "duration_ms": 1200,
      "created_at": "2026-04-04T12:00:01Z"
    },
    {
      "id": "...",
      "role": "orchestrator",
      "content": "{\"primary_concern\": \"drought stress\", ...}",
      "tool_name": null,
      "tool_input": null,
      "tool_output": null,
      "duration_ms": 890,
      "created_at": "2026-04-04T12:00:02Z"
    },
    {
      "id": "...",
      "role": "recommender",
      "content": "{\"action_type\": \"irrigate\", ...}",
      "tool_name": null,
      "tool_input": null,
      "tool_output": null,
      "duration_ms": 950,
      "created_at": "2026-04-04T12:00:03Z"
    },
    {
      "id": "...",
      "role": "final_response",
      "content": "Your cotton is showing early drought stress...",
      "tool_name": null,
      "tool_input": null,
      "tool_output": null,
      "duration_ms": null,
      "created_at": "2026-04-04T12:00:03Z"
    }
  ],
  "recommendations": [
    {
      "id": "...",
      "action_type": "irrigate",
      "urgency": "within_24h",
      "description": "Apply 2.5 inches of water to cotton field",
      "estimated_cost": "45.00",
      "risk_if_delayed": "12% yield loss if delayed beyond 3 days",
      "created_at": "2026-04-04T12:00:03Z"
    }
  ]
}
```

**Message roles in order:** `user` → `tool_call` (×3) → `field_agent` → `orchestrator` → `recommender` → `final_response`

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
    "updated_at": "2026-04-04T12:00:03Z"
  }
]
```

Sessions are returned most recent first. Both SMS and dashboard sessions appear here.

---

## Tool Endpoints (Debug/Display)

These are the raw data endpoints the agent calls internally. Useful for showing tool data in the dashboard UI.

### Weather

```
GET /api/v1/tools/weather/?lat=32.87&lng=-111.75
```

No auth required. Returns:
```json
{
  "temp_f": 105,
  "temp_c": 40.6,
  "humidity_pct": 12,
  "wind_mph": 8,
  "conditions": "clear sky",
  "uv_index": 11,
  "precipitation_forecast": [
    {"date": "2026-04-04", "precip_in": 0.0, "prob_pct": 0},
    {"date": "2026-04-05", "precip_in": 0.0, "prob_pct": 5}
  ]
}
```

### Crop Health (NDVI)

```
GET /api/v1/tools/crop-health/?field_id=a1b2c3d4-...
```

No auth required. Returns:
```json
{
  "field_id": "a1b2c3d4-...",
  "ndvi_score": 0.42,
  "stress_level": "moderate",
  "vegetation_trend": "declining",
  "last_satellite_date": "2026-04-03T14:30:00Z",
  "vegetation_fraction": 0.58
}
```

NDVI scale: 0.0-0.2 = severe, 0.2-0.4 = high, 0.4-0.6 = moderate, 0.6-0.8 = low (healthy), 0.8-1.0 = peak

### Soil Profile

```
GET /api/v1/tools/soil/?field_id=a1b2c3d4-...
```

No auth required. Returns:
```json
{
  "field_id": "a1b2c3d4-...",
  "soil_type": "Casa Grande sandy loam",
  "ph": 7.8,
  "organic_matter_pct": 1.2,
  "drainage_class": "well-drained",
  "water_holding_capacity": "low",
  "available_water_in_per_ft": 1.1
}
```

---

## Error Handling

| Status | Meaning | When |
|--------|---------|------|
| 200    | Success | Normal response |
| 201    | Created | Signup, field creation |
| 400    | Bad Request | Missing required fields, no fields registered |
| 401    | Unauthorized | Missing/expired JWT token |
| 404    | Not Found | Invalid field_id or session_id |
| 500    | Server Error | Agent engine failure (Gemini API down, etc.) |

**401 response shape:**
```json
{
  "detail": "Given token not valid for any token type",
  "code": "token_not_valid",
  "messages": [...]
}
```

**400/404 response shape:**
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
