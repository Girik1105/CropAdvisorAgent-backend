from django.urls import path

from .views import AgentMessageView, AgentTraceView, run_agent

urlpatterns = [
    path('run/', run_agent, name='run-agent'),
    path('message/', AgentMessageView.as_view(), name='agent-message'),
    path('trace/<uuid:session_id>/', AgentTraceView.as_view(), name='agent-trace'),
]
