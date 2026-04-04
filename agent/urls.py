from django.urls import path
from . import views

from .views import AgentMessageView, AgentTraceView

urlpatterns = [
    path('message/', AgentMessageView.as_view(), name='agent-message'),
    path('trace/<uuid:session_id>/', AgentTraceView.as_view(), name='agent-trace'),
]
