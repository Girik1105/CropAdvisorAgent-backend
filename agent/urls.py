from django.urls import path
from . import views

<<<<<<< HEAD
from .views import AgentMessageView, AgentTraceView

urlpatterns = [
    path('message/', AgentMessageView.as_view(), name='agent-message'),
    path('trace/<uuid:session_id>/', AgentTraceView.as_view(), name='agent-trace'),
]
=======
urlpatterns = [
    path('message/', views.run_agent, name='run_agent'),
]
>>>>>>> 089e137 (bug fixing)
