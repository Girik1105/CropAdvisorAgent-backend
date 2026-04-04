"""
URL configuration for CropAdvisor agent system.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/agent/', include('agent.urls')),
    path('api/v1/tools/', include('tools.urls')),
    path('api/v1/webhook/', include('webhooks.urls')),
]