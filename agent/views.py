import threading
import django

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .engine import CropAdvisorEngine
from .models import (
    ActionRecommendation, AgentMessage, AgentSession,
    CropHealthRecord, Field, SoilProfile, WeatherSnapshot,
)


def _run_health_check(session_id: str, field_id: str, user_message: str):
    """Run the full health check pipeline in a background thread."""
    django.db.connections.close_all()  # Fresh DB connections for thread
    try:
        session = AgentSession.objects.get(id=session_id)
        session.status = 'processing'
        session.save(update_fields=['status'])

        engine = CropAdvisorEngine()
        result = engine.run(
            field_id=field_id,
            user_message=user_message,
            session_id=session_id,
        )

        session.result = result
        session.status = 'completed'
        session.save(update_fields=['result', 'status'])
    except Exception as e:
        try:
            session = AgentSession.objects.get(id=session_id)
            session.status = 'failed'
            session.error_message = str(e)[:500]
            session.save(update_fields=['status', 'error_message'])
        except Exception:
            pass
    finally:
        django.db.connections.close_all()
from .serializers import (
    AgentMessageInputSerializer,
    AgentSessionSerializer,
    CropHealthRecordSerializer,
    FieldSerializer,
    SoilProfileSerializer,
    TraceSerializer,
    WeatherSnapshotSerializer,
)


class AgentMessageView(APIView):
    """Health Check — kicks off full 7-tool scan in a background thread."""

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
                return Response({"error": "No fields registered."}, status=400)

        channel = 'sms' if data.get('phone_number') else 'dashboard'
        session = AgentSession.objects.create(
            user=request.user,
            field=field,
            channel=channel,
            phone_number=data.get('phone_number', ''),
            status='processing',
        )

        # Run in background thread — return immediately
        thread = threading.Thread(
            target=_run_health_check,
            args=(str(session.id), str(field.id), data['message']),
            daemon=True,
        )
        thread.start()

        return Response({
            "session_id": str(session.id),
            "status": "processing",
        }, status=status.HTTP_202_ACCEPTED)


class AgentStatusView(APIView):
    """Poll for health check status."""

    def get(self, request, session_id):
        try:
            session = AgentSession.objects.get(id=session_id, user=request.user)
        except AgentSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)

        data = {"session_id": str(session.id), "status": session.status}

        if session.status == 'completed' and session.result:
            data["result"] = session.result
        elif session.status == 'failed':
            data["error"] = session.error_message or "Unknown error"

        return Response(data)


class AgentChatView(APIView):
    """Lightweight chat — answers questions using existing DB data, single Gemini call."""

    def get(self, request):
        """Return chat history for a field."""
        field_id = request.query_params.get('field_id')
        if not field_id:
            return Response({"error": "field_id required"}, status=400)

        sessions = AgentSession.objects.filter(
            user=request.user, field_id=field_id, channel='chat',
        ).order_by('created_at')

        all_msgs = AgentMessage.objects.filter(
            session__in=sessions, role__in=['user', 'agent'],
        ).order_by('-created_at')[:10]

        messages = [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in reversed(all_msgs)
        ]

        return Response({"messages": messages})

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
                return Response({"error": "No fields registered."}, status=400)

        session = AgentSession.objects.create(
            user=request.user,
            field=field,
            channel='chat',
        )

        try:
            engine = CropAdvisorEngine()
            result = engine.chat(
                field_id=str(field.id),
                user_message=data['message'],
                session_id=str(session.id),
            )
            return Response(result)
        except Exception as e:
            error_str = str(e)
            if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                return Response(
                    {"error": "AI rate limit reached. Please wait a moment and try again."},
                    status=429,
                )
            return Response({"error": f"Chat failed: {error_str}"}, status=500)


class AgentTraceView(APIView):
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
    serializer_class = FieldSerializer

    def get_queryset(self):
        return Field.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FieldDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = FieldSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'field_id'

    def get_queryset(self):
        return Field.objects.filter(owner=self.request.user)


class FieldSessionsView(generics.ListAPIView):
    serializer_class = AgentSessionSerializer

    def get_queryset(self):
        return AgentSession.objects.filter(
            field_id=self.kwargs['field_id'],
            user=self.request.user,
        ).order_by('-created_at')


class FieldWeatherHistoryView(generics.ListAPIView):
    """GET /api/v1/fields/<field_id>/weather/ — Weather snapshot history."""
    serializer_class = WeatherSnapshotSerializer

    def get_queryset(self):
        return WeatherSnapshot.objects.filter(
            field_id=self.kwargs['field_id'],
            field__owner=self.request.user,
        )


class FieldCropHealthView(generics.ListAPIView):
    """GET /api/v1/fields/<field_id>/crop-health/ — Crop health record history."""
    serializer_class = CropHealthRecordSerializer

    def get_queryset(self):
        return CropHealthRecord.objects.filter(
            field_id=self.kwargs['field_id'],
            field__owner=self.request.user,
        )


class FieldSoilProfileView(APIView):
    """GET /api/v1/fields/<field_id>/soil/ — Soil profile for a field."""

    def get(self, request, field_id):
        try:
            profile = SoilProfile.objects.get(
                field_id=field_id, field__owner=request.user,
            )
        except SoilProfile.DoesNotExist:
            return Response({"error": "No soil profile for this field"}, status=404)
        return Response(SoilProfileSerializer(profile).data)
