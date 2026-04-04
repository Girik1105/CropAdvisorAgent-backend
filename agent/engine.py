import json
import time
from typing import Dict, List, Any, Optional
from django.conf import settings
from google import genai
from .models import Field, AgentSession, AgentMessage, ActionRecommendation
from .prompts import FIELD_AGENT_PROMPT, ORCHESTRATOR_PROMPT, RECOMMENDER_PROMPT
from tools.services import get_weather, get_crop_health, get_soil_profile


class CropAdvisorEngine:
    """
    Multi-agent system orchestrator for crop advisory recommendations.

    Flow: Field Agent → Orchestrator → Recommender → Final Response
    Each "agent" is a Gemini API call with specialized system prompt.
    """

    def __init__(self):
        # Initialize Google Generative AI
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash-preview-04-17"

        # Define available tools for Gemini function calling
        self.tools = [
            genai.types.Tool(function_declarations=[
                genai.types.FunctionDeclaration(
                    name="get_weather",
                    description="Get current weather and 7-day precipitation forecast for a location.",
                    parameters=genai.types.Schema(
                        type="OBJECT",
                        properties={
                            "lat": genai.types.Schema(type="NUMBER"),
                            "lng": genai.types.Schema(type="NUMBER"),
                        },
                        required=["lat", "lng"]
                    )
                ),
                genai.types.FunctionDeclaration(
                    name="get_crop_health",
                    description="Get NDVI vegetation health score for a field.",
                    parameters=genai.types.Schema(
                        type="OBJECT",
                        properties={
                            "field_id": genai.types.Schema(type="STRING"),
                        },
                        required=["field_id"]
                    )
                ),
                genai.types.FunctionDeclaration(
                    name="get_soil_profile",
                    description="Get USDA soil profile for a field.",
                    parameters=genai.types.Schema(
                        type="OBJECT",
                        properties={
                            "field_id": genai.types.Schema(type="STRING"),
                        },
                        required=["field_id"]
                    )
                ),
            ])
        ]

    def run(self, field_id: str, user_message: str, session_id: str) -> Dict[str, Any]:
        """
        Main orchestration loop for multi-agent processing.

        Args:
            field_id: UUID of the field being queried
            user_message: Farmer's input message
            session_id: Active session UUID

        Returns:
            Dict with final recommendation, cost estimate, and reasoning trace
        """
        start_time = time.time()

        # Get field context
        try:
            field = Field.objects.get(id=field_id)
            session = AgentSession.objects.get(id=session_id)
        except (Field.DoesNotExist, AgentSession.DoesNotExist) as e:
            raise ValueError(f"Invalid field or session: {e}")

        # Save user message
        self._save_message(session, 'user', user_message)

        try:
            # 1. Field Agent — gathers data autonomously
            field_context = self._field_agent(field, session)

            # 2. Orchestrator — decides what analysis is needed
            plan = self._orchestrator_agent(field_context, user_message, session)

            # 3. Recommender — generates final action with cost estimates
            recommendation = self._recommender_agent(plan, field_context, user_message, session)

            # 4. Save structured recommendation to DB
            action_rec = self._save_recommendation(session, field, recommendation)

            # 5. Generate final response
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
                    "risk_if_delayed": action_rec.risk_if_delayed
                },
                "total_duration_ms": total_time
            }

        except Exception as e:
            error_msg = f"Agent processing failed: {str(e)}"
            self._save_message(session, 'agent', error_msg)
            raise

    def _field_agent(self, field: Field, session: AgentSession) -> Dict[str, Any]:
        """
        Field Agent: Autonomously gathers weather, crop health, and soil data.
        """
        start_time = time.time()

        prompt = FIELD_AGENT_PROMPT.format(
            field_name=field.name,
            crop_type=field.crop_type,
            field_id=str(field.id),
            lat=field.lat,
            lng=field.lng
        )

        # Call Gemini with tools
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"tools": self.tools}
        )

        # Process function calls
        tool_data = {}
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call'):
                tool_result = self._execute_tool(part.function_call, session)
                tool_data[part.function_call.name] = tool_result

        # Get final field context from agent
        final_response = self.client.models.generate_content(
            model=self.model_name,
            contents="Based on the tool results, provide a JSON summary of the field context."
        )

        duration = int((time.time() - start_time) * 1000)
        field_context = self._parse_agent_response(final_response.text)

        self._save_message(
            session, 'agent',
            json.dumps(field_context)
        )

        return field_context

    def _orchestrator_agent(self, field_context: Dict, user_message: str, session: AgentSession) -> Dict[str, Any]:
        """
        Orchestrator Agent: Analyzes field data and user intent to create action plan.
        """
        start_time = time.time()

        prompt = ORCHESTRATOR_PROMPT.format(
            user_message=user_message,
            field_context=json.dumps(field_context, indent=2)
        )

        response = self.client.models.generate_content(model=self.model_name, contents=prompt)
        plan = self._parse_agent_response(response.text)

        duration = int((time.time() - start_time) * 1000)
        self._save_message(
            session, 'agent',
            json.dumps(plan)
        )

        return plan

    def _recommender_agent(self, plan: Dict, field_context: Dict, user_message: str, session: AgentSession) -> Dict[str, Any]:
        """
        Recommender Agent: Generates specific, costed recommendations with risk analysis.
        """
        start_time = time.time()

        prompt = RECOMMENDER_PROMPT.format(
            plan=json.dumps(plan, indent=2),
            field_context=json.dumps(field_context, indent=2),
            user_message=user_message
        )

        response = self.client.models.generate_content(model=self.model_name, contents=prompt)
        recommendation = self._parse_agent_response(response.text)

        duration = int((time.time() - start_time) * 1000)
        self._save_message(
            session, 'agent',
            json.dumps(recommendation)
        )

        return recommendation

    def _execute_tool(self, function_call, session: AgentSession) -> Dict[str, Any]:
        """Execute a tool call and save the result to database."""
        start_time = time.time()
        tool_name = function_call.name
        tool_args = dict(function_call.args)

        tool_functions = {
            'get_weather': lambda args: get_weather(args['lat'], args['lng']),
            'get_crop_health': lambda args: get_crop_health(args['field_id']),
            'get_soil_profile': lambda args: get_soil_profile(args['field_id']),
        }

        try:
            if tool_name in tool_functions:
                tool_result = tool_functions[tool_name](tool_args)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            duration = int((time.time() - start_time) * 1000)

            # Save tool call and result
            self._save_message(
                session, 'tool_call',
                f"Called {tool_name} with {tool_args}",
                tool_name=tool_name,
                tool_input=tool_args,
                tool_output=tool_result
            )

            return tool_result

        except Exception as e:
            error_result = {"error": str(e)}
            duration = int((time.time() - start_time) * 1000)

            self._save_message(
                session, 'tool_result',
                f"Tool {tool_name} failed: {str(e)}",
                tool_name=tool_name,
                tool_input=tool_args,
                tool_output=error_result
            )

            return error_result

    def _save_message(self, session: AgentSession, role: str, content: str,
                     tool_name: str = None, tool_input: Dict = None,
                     tool_output: Dict = None):
        """Save a message to the database."""
        AgentMessage.objects.create(
            session=session,
            role=role,
            content=content,
            tool_name=tool_name or '',
            tool_input=tool_input,
            tool_output=tool_output
        )

    def _save_recommendation(self, session: AgentSession, field: Field, recommendation: Dict) -> ActionRecommendation:
        """Save structured recommendation to database."""
        return ActionRecommendation.objects.create(
            session=session,
            field=field,
            action_type=recommendation.get('action_type', 'no_action'),
            urgency=recommendation.get('urgency', 'monitor'),
            description=recommendation.get('description', ''),
            estimated_cost=recommendation.get('estimated_cost', 0.0),
            risk_if_delayed=recommendation.get('risk_if_delayed', '')
        )

    def _format_final_response(self, recommendation: Dict) -> str:
        """Format the final response text for SMS/API."""
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
        """Parse JSON response from agent, with fallback handling."""
        try:
            # Try to extract JSON from markdown code blocks
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()

            return json.loads(json_text)
        except (json.JSONDecodeError, ValueError):
            # Fallback: return raw text if JSON parsing fails
            return {"raw_response": response_text}