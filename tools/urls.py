from django.urls import path

from .views import CropHealthView, SoilProfileView, WeatherView

urlpatterns = [
    path('weather/', WeatherView.as_view(), name='weather'),
    path('crop-health/', CropHealthView.as_view(), name='crop-health'),
    path('soil/', SoilProfileView.as_view(), name='soil'),
]
