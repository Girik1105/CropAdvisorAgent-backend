from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
import json
from .engine import CropAdvisorEngine
from .models import Field, AgentSession

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

    # Create or get a default user for testing
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
