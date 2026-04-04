"""
Agent API views - entry points for triggering the multi-agent system.
"""

import json
import uuid
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Field, AgentSession
from .engine import CropAdvisorEngine


@api_view(['POST'])
def agent_message(request):
    """
    Main entry point for agent processing.

    POST /api/v1/agent/message/

    Expected payload:
    {
        "phone_number": "+16025551234",
        "message": "How's my field looking?",
        "field_id": "optional-uuid"
    }
    """
    try:
        # Extract request data
        phone_number = request.data.get('phone_number')
        message = request.data.get('message')
        field_id = request.data.get('field_id')

        if not phone_number or not message:
            return Response({
                'error': 'phone_number and message are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Auto-detect field from phone number if not provided
        if not field_id:
            try:
                field = Field.objects.get(owner_phone=phone_number)
                field_id = str(field.id)
            except Field.DoesNotExist:
                return Response({
                    'error': f'No field registered for phone number {phone_number}'
                }, status=status.HTTP_404_NOT_FOUND)
            except Field.MultipleObjectsReturned:
                return Response({
                    'error': 'Multiple fields found for this phone number. Please specify field_id.'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Create or get existing session
        field = Field.objects.get(id=field_id)
        session, created = AgentSession.objects.get_or_create(
            phone_number=phone_number,
            field=field,
            defaults={'id': uuid.uuid4()}
        )

        # Initialize and run the multi-agent engine
        engine = CropAdvisorEngine()
        result = engine.run(
            field_id=field_id,
            user_message=message,
            session_id=str(session.id)
        )

        return Response(result, status=status.HTTP_200_OK)

    except Field.DoesNotExist:
        return Response({
            'error': f'Field {field_id} not found'
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({
            'error': f'Agent processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def agent_trace(request, session_id):
    """
    Retrieve full reasoning trace for debugging/dashboard.

    GET /api/v1/agent/trace/{session_id}/
    """
    try:
        session = AgentSession.objects.get(id=session_id)
        messages = session.messages.all()

        trace_data = {
            'session_id': str(session.id),
            'phone_number': session.phone_number,
            'field': {
                'id': str(session.field.id),
                'name': session.field.name,
                'crop_type': session.field.crop_type,
                'lat': session.field.lat,
                'lng': session.field.lng
            },
            'messages': [
                {
                    'id': str(msg.id),
                    'role': msg.role,
                    'content': msg.content,
                    'tool_name': msg.tool_name,
                    'tool_input': msg.tool_input,
                    'tool_output': msg.tool_output,
                    'duration_ms': msg.duration_ms,
                    'created_at': msg.created_at.isoformat()
                }
                for msg in messages
            ],
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat()
        }

        return Response(trace_data, status=status.HTTP_200_OK)

    except AgentSession.DoesNotExist:
        return Response({
            'error': f'Session {session_id} not found'
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({
            'error': f'Failed to retrieve trace: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)