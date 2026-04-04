from rest_framework import serializers

from .models import ActionRecommendation, AgentMessage, AgentSession, Field


class FieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        fields = [
            'id', 'name', 'crop_type', 'lat', 'lng',
            'area_acres', 'soil_type', 'owner_phone',
        ]
        read_only_fields = ['id']


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
            'estimated_cost', 'risk_if_delayed', 'created_at',
        ]


class AgentSessionSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source='field.name', read_only=True)

    class Meta:
        model = AgentSession
        fields = [
            'id', 'phone_number', 'field', 'field_name',
            'channel', 'created_at', 'updated_at',
        ]


class TraceSerializer(serializers.Serializer):
    session = AgentSessionSerializer()
    messages = AgentMessageSerializer(many=True)
    recommendations = ActionRecommendationSerializer(many=True)
