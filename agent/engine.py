import json
import time
from typing import Dict, Any
from django.conf import settings
from google import genai
from google.genai import errors as genai_errors
from .models import Field, AgentSession, AgentMessage, ActionRecommendation
from .prompts import (
    FIELD_AGENT_PROMPT, ORCHESTRATOR_PROMPT, RECOMMENDER_PROMPT,
    INTENT_CLASSIFIER_PROMPT, GENERAL_QA_PROMPT,
)
from tools.services import (
    get_weather, get_crop_health, get_soil_profile,
    get_market_prices, get_pest_risk, get_water_usage, get_growth_stage,
)


class CropAdvisorEngine:
    """
    Multi-agent system orchestrator for crop advisory recommendations.

    Flow:
      user msg → _classify_intent()
        ├─ "action_needed"    → Field Agent → Orchestrator → Recommender → Response
        └─ "general_question" → General QA Agent → Response
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options={"api_version": "v1"})
        self.model_name = "gemini-2.5-flash"

    def run(self, field_id: str, user_message: str, session_id: str) -> Dict[str, Any]:
        """
        Main orchestration loop with intent-based routing.
        """
        start_time = time.time()

        try:
            field = Field.objects.get(id=field_id)
            session = AgentSession.objects.get(id=session_id)
        except (Field.DoesNotExist, AgentSession.DoesNotExist) as e:
            raise ValueError(f"Invalid field or session: {e}")

        # Save user message
        self._save_message(session, 'user', user_message)

        try:
            # Classify intent
            intent = self._classify_intent(user_message)

            if intent == "general_question":
                # General QA path — lighter, no structured recommendation
                response_text = self._general_qa_agent(user_message, field, session)
                self._save_message(session, 'agent', response_text)

                total_time = int((time.time() - start_time) * 1000)
                return {
                    "session_id": str(session_id),
                    "response": response_text,
                    "recommendation": None,
                    "total_duration_ms": total_time,
                }
            else:
                # Full action pipeline
                # 1. Field Agent — gathers all data
                field_context = self._field_agent(field, session)

                # 2. Orchestrator — creates action plan
                plan = self._orchestrator_agent(field_context, user_message, session)

                # 3. Recommender — costed recommendation
                recommendation = self._recommender_agent(plan, field_context, user_message, session)

                # 4. Save structured recommendation
                action_rec = self._save_recommendation(session, field, recommendation)

                # 5. Final response
                response_text = self._format_final_response(recommendation)
                self._save_message(session, 'agent', response_text)

                total_time = int((time.time() - start_time) * 1000)

                return {
                    "session_id": str(session_id),
                    "response": response_text,
                    "recommendation": {
                        "action_type": action_rec.action_type,
                        "urgency": action_rec.urgency,
                        "description": action_rec.description,
                        "estimated_cost": float(action_rec.estimated_cost),
                        "risk_if_delayed": action_rec.risk_if_delayed,
                    },
                    "total_duration_ms": total_time,
                }

        except Exception as e:
            error_msg = f"Agent processing failed: {str(e)}"
            self._save_message(session, 'agent', error_msg)
            raise

    # ─── Intent Classification ───

    def _classify_intent(self, user_message: str) -> str:
        """Quick Gemini call to classify the user's intent."""
        prompt = INTENT_CLASSIFIER_PROMPT.format(user_message=user_message)
        try:
            result = self._gemini_call(prompt).strip().lower()
            if "general" in result:
                return "general_question"
            return "action_needed"
        except Exception:
            return "action_needed"  # default to full pipeline

    # ─── General QA Agent ───

    def _general_qa_agent(self, user_message: str, field: Field, session: AgentSession) -> str:
        """
        Answer general agricultural questions without the full tool pipeline.
        Still has basic field context for personalization.
        """
        field_context_section = (
            f"FIELD CONTEXT (for personalization):\n"
            f"- Field: {field.name}\n"
            f"- Crop: {field.crop_type}\n"
            f"- Location: {field.lat}, {field.lng}\n"
            f"- Soil type: {field.soil_type}\n"
            f"- Area: {field.area_acres} acres"
        )

        prompt = GENERAL_QA_PROMPT.format(
            user_message=user_message,
            field_context_section=field_context_section,
        )

        self._save_message(
            session, 'tool_call',
            'Routed to General QA Agent (no field-specific tools needed)',
            tool_name='intent_classifier',
            tool_input={'message': user_message},
            tool_output={'intent': 'general_question'},
            duration_ms=0,
        )

        return self._gemini_call(prompt).strip()

    # ─── Field Agent (7 tools) ───

    def _field_agent(self, field: Field, session: AgentSession) -> Dict[str, Any]:
        """
        Field Agent: Autonomously gathers weather, crop health, soil, market,
        pest risk, water usage, and growth stage data.
        """
        # 1. Weather
        start = time.time()
        weather = get_weather(field.lat, field.lng, field=field, session=session)
        self._save_message(
            session, 'tool_call',
            f"Called get_weather with lat={field.lat}, lng={field.lng}",
            tool_name='get_weather',
            tool_input={'lat': field.lat, 'lng': field.lng},
            tool_output=weather,
            duration_ms=int((time.time() - start) * 1000),
        )

        # 2. Crop Health
        start = time.time()
        crop_health = get_crop_health(str(field.id), field=field)
        self._save_message(
            session, 'tool_call',
            f"Called get_crop_health with field_id={field.id}",
            tool_name='get_crop_health',
            tool_input={'field_id': str(field.id)},
            tool_output=crop_health,
            duration_ms=int((time.time() - start) * 1000),
        )

        # 3. Soil Profile
        start = time.time()
        soil = get_soil_profile(str(field.id), field=field)
        self._save_message(
            session, 'tool_call',
            f"Called get_soil_profile with field_id={field.id}",
            tool_name='get_soil_profile',
            tool_input={'field_id': str(field.id)},
            tool_output=soil,
            duration_ms=int((time.time() - start) * 1000),
        )

        # 4. Market Prices
        start = time.time()
        market = get_market_prices(field.crop_type, field=field, session=session)
        self._save_message(
            session, 'tool_call',
            f"Called get_market_prices with crop_type={field.crop_type}",
            tool_name='get_market_prices',
            tool_input={'crop_type': field.crop_type},
            tool_output=market,
            duration_ms=int((time.time() - start) * 1000),
        )

        # 5. Pest Risk (uses weather data already fetched)
        start = time.time()
        pest_risk = get_pest_risk(
            field.crop_type,
            weather.get('temp_f', 90),
            weather.get('humidity_pct', 30),
            field=field,
            session=session,
        )
        self._save_message(
            session, 'tool_call',
            f"Called get_pest_risk with crop={field.crop_type}, temp={weather.get('temp_f')}°F, humidity={weather.get('humidity_pct')}%",
            tool_name='get_pest_risk',
            tool_input={'crop_type': field.crop_type, 'temp_f': weather.get('temp_f'), 'humidity_pct': weather.get('humidity_pct')},
            tool_output=pest_risk,
            duration_ms=int((time.time() - start) * 1000),
        )

        # 6. Water Usage (uses weather + soil data)
        start = time.time()
        water = get_water_usage(
            str(field.id),
            field=field,
            session=session,
            weather_data=weather,
            soil_data=soil,
        )
        self._save_message(
            session, 'tool_call',
            f"Called get_water_usage with field_id={field.id}",
            tool_name='get_water_usage',
            tool_input={'field_id': str(field.id)},
            tool_output=water,
            duration_ms=int((time.time() - start) * 1000),
        )

        # 7. Growth Stage
        start = time.time()
        growth = get_growth_stage(field.crop_type)
        self._save_message(
            session, 'tool_call',
            f"Called get_growth_stage with crop_type={field.crop_type}",
            tool_name='get_growth_stage',
            tool_input={'crop_type': field.crop_type},
            tool_output=growth,
            duration_ms=int((time.time() - start) * 1000),
        )

        return {
            "field_name": field.name,
            "crop_type": field.crop_type,
            "area_acres": field.area_acres,
            "weather": weather,
            "crop_health": crop_health,
            "soil": soil,
            "market_prices": market,
            "pest_risk": pest_risk,
            "water_usage": water,
            "growth_stage": growth,
        }

    # ─── Orchestrator & Recommender ───

    def _orchestrator_agent(self, field_context: Dict, user_message: str, session: AgentSession) -> Dict[str, Any]:
        """Orchestrator Agent: Analyzes field data and creates action plan."""
        start_time = time.time()

        prompt = ORCHESTRATOR_PROMPT.format(
            user_message=user_message,
            field_context=json.dumps(field_context, indent=2)
        )

        plan = self._parse_agent_response(self._gemini_call(prompt))

        self._save_message(session, 'agent', json.dumps(plan))
        return plan

    def _recommender_agent(self, plan: Dict, field_context: Dict, user_message: str, session: AgentSession) -> Dict[str, Any]:
        """Recommender Agent: Generates costed recommendations with risk analysis."""
        start_time = time.time()

        prompt = RECOMMENDER_PROMPT.format(
            plan=json.dumps(plan, indent=2),
            field_context=json.dumps(field_context, indent=2),
            user_message=user_message
        )

        recommendation = self._parse_agent_response(self._gemini_call(prompt))

        self._save_message(session, 'agent', json.dumps(recommendation))
        return recommendation

    # ─── Helpers ───

    def _gemini_call(self, prompt: str, max_retries: int = 3) -> str:
        """Call Gemini with retry logic for rate limits (429)."""
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name, contents=prompt
                )
                return response.text
            except genai_errors.ClientError as e:
                if '429' in str(e) and attempt < max_retries - 1:
                    wait = 10 * (attempt + 1)
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError("Gemini API call failed after retries")

    def _save_message(self, session: AgentSession, role: str, content: str,
                     tool_name: str = None, tool_input: Dict = None,
                     tool_output: Dict = None, duration_ms: int = None):
        AgentMessage.objects.create(
            session=session,
            role=role,
            content=content,
            tool_name=tool_name or '',
            tool_input=tool_input,
            tool_output=tool_output,
            duration_ms=duration_ms,
        )

    def _save_recommendation(self, session: AgentSession, field: Field, recommendation: Dict) -> ActionRecommendation:
        return ActionRecommendation.objects.create(
            session=session,
            field=field,
            action_type=recommendation.get('action_type', 'no_action'),
            urgency=recommendation.get('urgency', 'monitor'),
            description=recommendation.get('description', ''),
            estimated_cost=recommendation.get('estimated_cost', 0.0),
            cost_breakdown=recommendation.get('cost_breakdown', ''),
            risk_if_delayed=recommendation.get('risk_if_delayed', ''),
            timing_rationale=recommendation.get('timing_rationale', ''),
            implementation_steps=recommendation.get('implementation_steps', []),
        )

    def _format_final_response(self, recommendation: Dict) -> str:
        action = recommendation.get('action_type', '').replace('_', ' ').title()
        cost = recommendation.get('estimated_cost', 0)
        risk = recommendation.get('risk_if_delayed', '')

        response = recommendation.get('description', '')
        if cost > 0:
            response += f" Estimated cost: ${cost:.0f}."
        if risk:
            response += f" {risk}"

        return response

    def _parse_agent_response(self, response_text: str) -> Dict[str, Any]:
        try:
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()
            return json.loads(json_text)
        except (json.JSONDecodeError, ValueError):
            return {"raw_response": response_text}
