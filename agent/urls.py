from django.urls import path
from .views import AgentMessageView, AgentStatusView, AgentChatView, AgentTraceView

urlpatterns = [
    path('message/', AgentMessageView.as_view(), name='agent-message'),
    path('status/<uuid:session_id>/', AgentStatusView.as_view(), name='agent-status'),
    path('chat/', AgentChatView.as_view(), name='agent-chat'),
    path('trace/<uuid:session_id>/', AgentTraceView.as_view(), name='agent-trace'),
]
