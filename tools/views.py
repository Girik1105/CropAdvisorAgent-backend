from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import get_crop_health, get_soil_profile, get_weather


class WeatherView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        if not lat or not lng:
            return Response({"error": "lat and lng are required"}, status=400)
        data = get_weather(float(lat), float(lng))
        return Response(data)


class CropHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        field_id = request.query_params.get('field_id')
        if not field_id:
            return Response({"error": "field_id is required"}, status=400)
        data = get_crop_health(field_id)
        return Response(data)


class SoilProfileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        field_id = request.query_params.get('field_id')
        if not field_id:
            return Response({"error": "field_id is required"}, status=400)
        data = get_soil_profile(field_id)
        return Response(data)
