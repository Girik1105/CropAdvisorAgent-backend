"""
SMS webhook views - Twilio integration that calls the same agent engine.
"""

import uuid
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from twilio.twiml.messaging_response import MessagingResponse


from agent.models import Field, AgentSession
from agent.engine import CropAdvisorEngine


@csrf_exempt
@require_http_methods(["POST"])
def sms_webhook(request):
    """
    Twilio SMS webhook handler.

    POST /api/v1/webhook/sms/

    Twilio sends form data:
    - From: sender phone number
    - Body: SMS message body
    - To: Twilio number
    - MessageSid: Twilio message ID
    """
    try:
        # Extract Twilio webhook data
        from_number = request.POST.get('From')
        message_body = request.POST.get('Body', '').strip()
        to_number = request.POST.get('To')
        message_sid = request.POST.get('MessageSid')

        if not from_number or not message_body:
            return _error_response("Invalid SMS format")

        # Find field registered to this phone number
        try:
            field = Field.objects.get(owner_phone=from_number)
        except Field.DoesNotExist:
            return _error_response(
                f"No field registered for {from_number}. Contact support to register your field."
            )
        except Field.MultipleObjectsReturned:
            # Default to first field if multiple exist
            field = Field.objects.filter(owner_phone=from_number).first()

        # Create or get existing session
        session, created = AgentSession.objects.get_or_create(
            phone_number=from_number,
            field=field,
            defaults={'id': uuid.uuid4()}
        )

        # Run the same multi-agent engine
        engine = CropAdvisorEngine()
        result = engine.run(
            field_id=str(field.id),
            user_message=message_body,
            session_id=str(session.id)
        )

        # Return TwiML response with agent recommendation
        response_text = result.get('response', 'Sorry, I encountered an error processing your request.')

        # Truncate response if too long for SMS (1600 char limit)
        if len(response_text) > 1500:
            response_text = response_text[:1497] + "..."

        twiml_response = MessagingResponse()
        twiml_response.message(response_text)

        return HttpResponse(str(twiml_response), content_type='text/xml')

    except Exception as e:
        return _error_response(f"Processing failed: {str(e)}")


def _error_response(error_message: str) -> HttpResponse:
    """Generate TwiML error response."""
    twiml_response = MessagingResponse()
    twiml_response.message(f"CropAdvisor Error: {error_message}")
    return HttpResponse(str(twiml_response), content_type='text/xml')