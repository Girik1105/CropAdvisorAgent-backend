import json

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .engine import CropAdvisorEngine
from .models import ActionRecommendation, AgentMessage, AgentSession, Field
from .serializers import (
    AgentMessageInputSerializer,
    AgentSessionSerializer,
    FieldSerializer,
    TraceSerializer,
)


# ── Quick test endpoint (no auth, for debugging) ──────────────────────

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def run_agent(request):
    data = json.loads(request.body)
    field_id = data.get('field_id')
    message = data.get('message')
    phone_number = data.get('phone_number')

    field = Field.objects.get(id=field_id)

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username='test_farmer',
        defaults={'email': 'test@farmer.com'}
    )

    session, _ = AgentSession.objects.get_or_create(
        phone_number=phone_number,
        field=field,
        user=user,
        defaults={'channel': 'sms'}
    )

    engine = CropAdvisorEngine()
    result = engine.run(
        field_id=field_id,
        user_message=message,
        session_id=str(session.id)
    )

    return JsonResponse(result)


# ── Production endpoints (JWT auth) ───────────────────────────────────

class AgentMessageView(APIView):
    """POST /api/v1/agent/message/ — Main entry point for agent interaction."""

    def post(self, request):
        serializer = AgentMessageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        field_id = data.get('field_id')
        if field_id:
            try:
                field = Field.objects.get(id=field_id, owner=request.user)
            except Field.DoesNotExist:
                return Response({"error": "Field not found"}, status=404)
        else:
            field = Field.objects.filter(owner=request.user).first()
            if not field:
                return Response(
                    {"error": "No fields registered. Create a field first."},
                    status=400,
                )

        channel = 'sms' if data.get('phone_number') else 'dashboard'
        session, _ = AgentSession.objects.get_or_create(
            user=request.user,
            field=field,
            channel=channel,
            defaults={'phone_number': data.get('phone_number', '')},
        )

        try:
            engine = CropAdvisorEngine()
            result = engine.run(
                field_id=str(field.id),
                user_message=data['message'],
                session_id=str(session.id),
            )
            return Response(result)
        except Exception as e:
            return Response(
                {"error": f"Agent processing failed: {str(e)}"},
                status=500,
            )


class AgentTraceView(APIView):
    """GET /api/v1/agent/trace/<session_id>/ — Full reasoning trace."""

    def get(self, request, session_id):
        try:
            session = AgentSession.objects.select_related('field').get(
                id=session_id, user=request.user,
            )
        except AgentSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)

        messages = AgentMessage.objects.filter(session=session)
        recommendations = ActionRecommendation.objects.filter(session=session)

        serializer = TraceSerializer({
            'session': session,
            'messages': messages,
            'recommendations': recommendations,
        })
        return Response(serializer.data)


class FieldListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/fields/ — List or create fields for the authenticated user."""
    serializer_class = FieldSerializer

    def get_queryset(self):
        return Field.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FieldSessionsView(generics.ListAPIView):
    """GET /api/v1/fields/<field_id>/sessions/ — List sessions for a field."""
    serializer_class = AgentSessionSerializer

    def get_queryset(self):
        return AgentSession.objects.filter(
            field_id=self.kwargs['field_id'],
            user=self.request.user,
        ).order_by('-created_at')
