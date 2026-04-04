from django.http import HttpResponse
from rest_framework.parsers import FormParser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from agent.engine import CropAdvisorEngine
from agent.models import AgentSession, Field


class SmsWebhookView(APIView):
    """POST /api/v1/webhook/sms/ — Twilio inbound SMS webhook."""
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [FormParser]

    def post(self, request):
        body = request.data.get('Body', '')
        from_number = request.data.get('From', '')

        if not body or not from_number:
            return self._twiml("Sorry, we couldn't process your message.")

        # Look up field by phone number
        field = Field.objects.filter(owner_phone=from_number).first()
        if not field:
            return self._twiml(
                "Your phone number is not registered. "
                "Please contact support to set up your field."
            )

        # Get or create session
        session, _ = AgentSession.objects.get_or_create(
            user=field.owner,
            field=field,
            channel='sms',
            defaults={'phone_number': from_number},
        )

        # Run agent
        try:
            engine = CropAdvisorEngine()
            result = engine.run(
                field_id=str(field.id),
                user_message=body,
                session_id=str(session.id),
            )
            return self._twiml(result['response'])
        except Exception as e:
            return self._twiml(
                "Sorry, we're having trouble processing your request. "
                "Please try again shortly."
            )

    def _twiml(self, message: str) -> HttpResponse:
        xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{message}</Message></Response>'
        return HttpResponse(xml, content_type='text/xml')
