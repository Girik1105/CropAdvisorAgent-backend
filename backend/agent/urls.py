"""
URL patterns for agent API endpoints.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('message/', views.agent_message, name='agent_message'),
    path('trace/<uuid:session_id>/', views.agent_trace, name='agent_trace'),
]