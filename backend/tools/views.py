"""
Tool API endpoints for the CropAdvisor agent system.
"""

import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse

from .weather import get_weather_data
from .crop_health import get_crop_health_data
from .soil import get_soil_data


@api_view(['GET'])
def weather_tool(request):
    """
    GET /api/v1/tools/weather/

    Query params:
    - lat: float (required)
    - lng: float (required)

    Returns current weather + 7-day forecast
    """
    try:
        lat = float(request.GET.get('lat'))
        lng = float(request.GET.get('lng'))
    except (TypeError, ValueError):
        return Response({
            'error': 'lat and lng parameters required as numbers'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        weather_data = get_weather_data(lat, lng)
        return Response(weather_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': f'Weather data fetch failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def crop_health_tool(request):
    """
    GET /api/v1/tools/crop-health/

    Query params:
    - field_id: UUID (required)

    Returns NDVI-based crop health assessment
    """
    field_id = request.GET.get('field_id')
    if not field_id:
        return Response({
            'error': 'field_id parameter required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        crop_health_data = get_crop_health_data(field_id)
        return Response(crop_health_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': f'Crop health data fetch failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def soil_tool(request):
    """
    GET /api/v1/tools/soil/

    Query params:
    - field_id: UUID (required)

    Returns USDA soil profile data
    """
    field_id = request.GET.get('field_id')
    if not field_id:
        return Response({
            'error': 'field_id parameter required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        soil_data = get_soil_data(field_id)
        return Response(soil_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': f'Soil data fetch failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)