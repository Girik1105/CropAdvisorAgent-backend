from rest_framework import serializers

from .models import (
    ActionRecommendation, AgentMessage, AgentSession,
    CropHealthRecord, Field, SoilProfile, WeatherSnapshot,
)


class FieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        fields = [
            'id', 'name', 'crop_type', 'lat', 'lng',
            'area_acres', 'soil_type', 'owner_phone',
        ]
        read_only_fields = ['id']


class WeatherSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherSnapshot
        fields = [
            'id', 'field', 'temp_f', 'temp_c', 'humidity_pct',
            'wind_mph', 'conditions', 'uv_index',
            'precipitation_forecast', 'created_at',
        ]


class CropHealthRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropHealthRecord
        fields = [
            'id', 'field', 'ndvi_score', 'stress_level',
            'vegetation_trend', 'vegetation_fraction',
            'last_satellite_date', 'created_at',
        ]


class SoilProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoilProfile
        fields = [
            'id', 'field', 'soil_type', 'ph', 'organic_matter_pct',
            'drainage_class', 'water_holding_capacity',
            'available_water_in_per_ft', 'updated_at',
        ]


class AgentMessageInputSerializer(serializers.Serializer):
    message = serializers.CharField()
    field_id = serializers.UUIDField(required=False)
    phone_number = serializers.CharField(required=False, default='')


class AgentMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentMessage
        fields = [
            'id', 'role', 'content', 'tool_name',
            'tool_input', 'tool_output', 'duration_ms', 'created_at',
        ]


class ActionRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionRecommendation
        fields = [
            'id', 'action_type', 'urgency', 'description',
            'estimated_cost', 'cost_breakdown', 'risk_if_delayed',
            'timing_rationale', 'implementation_steps', 'created_at',
        ]


class AgentSessionSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source='field.name', read_only=True)
    crop_type = serializers.CharField(source='field.crop_type', read_only=True)
    message = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    recommendation_action = serializers.SerializerMethodField()
    recommendation_urgency = serializers.SerializerMethodField()
    tool_count = serializers.SerializerMethodField()

    class Meta:
        model = AgentSession
        fields = [
            'id', 'phone_number', 'field', 'field_name', 'crop_type',
            'channel', 'status', 'message',
            'recommendation_action', 'recommendation_urgency', 'tool_count',
            'created_at', 'updated_at',
        ]

    def get_message(self, obj):
        msg = obj.messages.filter(role='user').first()
        return msg.content[:120] if msg else None

    def get_recommendation_action(self, obj):
        rec = obj.recommendations.first()
        return rec.action_type if rec else None

    def get_recommendation_urgency(self, obj):
        rec = obj.recommendations.first()
        return rec.urgency if rec else None

    def get_tool_count(self, obj):
        return obj.messages.filter(role='tool_call').count()


class TraceSerializer(serializers.Serializer):
    session = AgentSessionSerializer()
    messages = AgentMessageSerializer(many=True)
    recommendations = ActionRecommendationSerializer(many=True)
