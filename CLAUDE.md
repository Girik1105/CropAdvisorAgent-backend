# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CropAdvisor is a Gemini-powered agricultural AI agent built for Innovation Hacks 2.0 (April 3-5, 2026). It's an autonomous SMS/voice system where farmers text for real-time crop management advice. The agent integrates weather, NDVI satellite data, and soil reports to provide specific recommendations with cost estimates.

## Architecture

This is a multi-service system with clear separation of concerns:

- **Backend**: Django 5 + DRF serving agent orchestration and tool APIs
- **Frontend**: Next.js 14 (App Router) for reasoning trace dashboard  
- **Agent Engine**: Gemini 1.5 Flash with function calling for autonomous decision making
- **Communication**: Twilio (SMS/WhatsApp) and ElevenLabs (voice)
- **Infrastructure**: Google Cloud Platform (Cloud Functions/Cloud Run)

## Team Structure

Work is divided into three parallel tracks:
- **P1**: Multi-agent system (Gemini orchestration, cost estimation, reasoning)  
- **P2**: Data tools (weather APIs, NDVI, soil data)
- **P3**: Frontend (dashboard, SMS webhooks, voice integration)

## Core Agent Flow

The agent follows a **sense → reason → act → notify** loop:
1. **Sense**: Farmer texts → agent calls `get_weather()`, `get_crop_health()`, `get_soil_profile()`
2. **Reason**: Gemini synthesizes data considering crop type, growth stage, historical patterns
3. **Act**: Generate recommendation with cost estimate and risk quantification
4. **Notify**: Respond via SMS + optional voice audio via ElevenLabs

## Key APIs & Integration Points

### Agent Orchestration (P1 responsibility)
- `POST /api/v1/agent/message/` - Main entry point, triggers full agent loop
- `backend/agent/engine.py` - Core Gemini function-calling orchestration
- `backend/agent/prompts.py` - Agricultural expertise system prompts
- Cost estimation algorithms (irrigation ~$45, fertilizer, yield loss calculations)

### Data Tools (P2 responsibility)  
- `GET /api/v1/tools/weather/` - OpenWeatherMap integration
- `GET /api/v1/tools/crop-health/` - NDVI vegetation stress (0.0-1.0 scale)
- `GET /api/v1/tools/soil/` - USDA soil profile data

### Frontend/Communication (P3 responsibility)
- `POST /api/v1/webhook/sms/` - Twilio SMS webhook handler
- Next.js dashboard showing reasoning traces and tool call visualization
- ElevenLabs voice generation for accessibility

## Development Commands

```bash
# Backend setup
cd backend
python manage.py migrate
python manage.py runserver

# Frontend setup  
cd frontend
npm install
npm run dev

# Run tests
python manage.py test
npm test
```

## Data Models

Critical models defined in `backend/agent/models.py`:
- **Field**: Crop location with coordinates, crop type, soil data
- **AgentSession**: Conversation thread with farmer
- **AgentMessage**: Individual messages with tool call traces
- **ActionRecommendation**: Structured recommendations with costs/risks

## Function Calling Tools

Gemini agent has access to three tools:
- `get_weather(lat, lng)` - Current conditions + 7-day forecast
- `get_crop_health(field_id)` - NDVI score and vegetation stress level
- `get_soil_profile(field_id)` - USDA soil type, pH, drainage, water capacity

## Hackathon Scope

**Demo scenario**: Cotton farmer in Casa Grande, AZ texts "How's my field looking?" → Agent autonomously gathers data → Responds: "Your cotton is showing early drought stress. Irrigate within 24 hours. Estimated water cost: $45. Delaying 3+ days risks 12% yield loss."

**Target**: Google Track (Vertex AI/Gemini) + ElevenLabs voice integration for MLH co-submission.

**Out of scope**: Multi-tenant users, live satellite integration, mobile apps, multi-language support.

## Configuration

Requires setup for:
- Google Cloud Project with Vertex AI enabled
- Twilio SMS webhook endpoint  
- ElevenLabs API key (from MLH promo code)
- OpenWeatherMap API key

Credentials managed via Django settings with environment variables.