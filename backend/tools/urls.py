"""
URL patterns for tool API endpoints.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('weather/', views.weather_tool, name='weather_tool'),
    path('crop-health/', views.crop_health_tool, name='crop_health_tool'),
    path('soil/', views.soil_tool, name='soil_tool'),
]