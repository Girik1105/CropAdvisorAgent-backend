# Twilio SMS Integration Guide

## Overview

CropAdvisor uses Twilio to let farmers interact with the AI agent via SMS. A farmer texts your Twilio number, the backend runs the full agent pipeline, and responds with a recommendation — all over SMS.

## How It Works

```
Farmer sends SMS
    → Twilio receives it
    → Twilio POSTs to your webhook URL
    → POST /api/v1/webhook/sms/
    → Backend looks up field by phone number
    → Runs CropAdvisorEngine (3-agent pipeline)
    → Returns TwiML <Response><Message>...</Message></Response>
    → Twilio delivers the reply SMS to the farmer
```

## Webhook Endpoint

### `POST /api/v1/webhook/sms/`

**Auth:** None (AllowAny) — Twilio cannot send JWT tokens. The webhook is open.

**Content-Type:** `application/x-www-form-urlencoded` (Twilio sends form data, not JSON)

**Twilio sends these fields:**

| Field      | Example                  | Description                    |
|------------|--------------------------|--------------------------------|
| From       | +16025551234             | Farmer's phone number (E.164)  |
| Body       | How's my field looking?  | The SMS message text           |
| To         | +18001234567             | Your Twilio phone number       |
| MessageSid | SM1234abcd...            | Unique message identifier      |

**Response format:** TwiML XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>Your cotton is showing early drought stress. Irrigate within 24 hours. Estimated water cost: $45. Delaying 3+ days risks 12% yield loss.</Message>
</Response>
```

**Error responses** (still TwiML so the farmer gets a message):
- Phone not registered: "Your phone number is not registered. Please contact support to set up your field."
- Engine failure: "Sorry, we're having trouble processing your request. Please try again shortly."

## Phone → Field → User Lookup

The webhook uses this chain to identify who's texting:

1. Extract `From` phone number from Twilio POST data
2. Query `Field.objects.filter(owner_phone=From)` — find field matching the phone
3. Get user from `field.owner` (Field has a required FK to Django User)
4. Create or reuse an `AgentSession` with `channel='sms'`

**Important:** The farmer's phone number must match `owner_phone` on a Field record exactly (E.164 format: `+1XXXXXXXXXX`). If no match is found, the farmer gets an error SMS.

## Twilio Console Setup

### 1. Get a Phone Number
- Go to [Twilio Console](https://console.twilio.com/) → Phone Numbers → Buy a Number
- Choose a number with SMS capability

### 2. Configure the Webhook
- Go to Phone Numbers → Manage → Active Numbers → click your number
- Under **Messaging** → **A message comes in**:
  - Set to **Webhook**
  - URL: `https://your-domain.com/api/v1/webhook/sms/`
  - Method: **HTTP POST**

### 3. For Local Development (ngrok)

```bash
# Start your Django server
python manage.py runserver 8000

# In another terminal, expose it via ngrok
ngrok http 8000

# Copy the ngrok URL (e.g. https://abc123.ngrok.io)
# Set it in Twilio console as: https://abc123.ngrok.io/api/v1/webhook/sms/
```

## Environment Variables

Add these to your `.env` file:

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=
```

These are defined in `config/settings.py` and loaded via `os.getenv()`. Currently used for reference — the webhook itself doesn't validate Twilio signatures yet (hackathon scope). For production, add signature validation using `twilio.request_validator`.

## Registering a Farmer's Phone

For SMS to work, the farmer's phone must be linked to a Field. This is done via the dashboard:

```
POST /api/v1/fields/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "name": "North 40",
  "crop_type": "cotton",
  "lat": 32.87,
  "lng": -111.75,
  "area_acres": 40,
  "soil_type": "sandy loam",
  "owner_phone": "+16025551234"   ← farmer's phone number
}
```

Now when `+16025551234` texts the Twilio number, the backend finds this field and runs the agent.

## Testing Without Twilio

You can simulate a Twilio webhook locally:

```bash
curl -X POST http://localhost:8000/api/v1/webhook/sms/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=+16025551234&Body=How%20is%20my%20field%20looking%3F&To=+18001234567"
```

The response will be TwiML XML.

## Session Tracking

Every SMS conversation creates an `AgentSession` with `channel='sms'`. These sessions are visible on the dashboard via:
- `GET /api/v1/fields/<field_id>/sessions/` — lists all sessions (both SMS and dashboard)
- `GET /api/v1/agent/trace/<session_id>/` — full reasoning trace for any session

This means the dashboard user can see what happened when a farmer texted in.
