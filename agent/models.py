import uuid

from django.conf import settings
from django.db import models


class Field(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fields'
    )
    name = models.CharField(max_length=255)
    crop_type = models.CharField(max_length=100)
    lat = models.FloatField()
    lng = models.FloatField()
    area_acres = models.FloatField()
    soil_type = models.CharField(max_length=100)
    owner_phone = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} ({self.crop_type})"


class AgentSession(models.Model):
    class Channel(models.TextChoices):
        SMS = 'sms', 'SMS'
        DASHBOARD = 'dashboard', 'Dashboard'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessions'
    )
    phone_number = models.CharField(max_length=20, blank=True, default='')
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='sessions')
    channel = models.CharField(max_length=10, choices=Channel.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.id} ({self.channel})"


class AgentMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        AGENT = 'agent', 'Agent'
        TOOL_CALL = 'tool_call', 'Tool Call'
        TOOL_RESULT = 'tool_result', 'Tool Result'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        AgentSession, on_delete=models.CASCADE, related_name='messages'
    )
    role = models.CharField(max_length=15, choices=Role.choices)
    content = models.TextField()
    tool_name = models.CharField(max_length=100, blank=True, null=True)
    tool_input = models.JSONField(blank=True, null=True)
    tool_output = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role} message in {self.session_id}"


class ActionRecommendation(models.Model):
    class ActionType(models.TextChoices):
        IRRIGATE = 'irrigate', 'Irrigate'
        FERTILIZE = 'fertilize', 'Fertilize'
        PEST_ALERT = 'pest_alert', 'Pest Alert'
        HARVEST = 'harvest', 'Harvest'
        NO_ACTION = 'no_action', 'No Action'

    class Urgency(models.TextChoices):
        IMMEDIATE = 'immediate', 'Immediate'
        WITHIN_24H = 'within_24h', 'Within 24 Hours'
        WITHIN_3D = 'within_3d', 'Within 3 Days'
        MONITOR = 'monitor', 'Monitor'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        AgentSession, on_delete=models.CASCADE, related_name='recommendations'
    )
    field = models.ForeignKey(
        Field, on_delete=models.CASCADE, related_name='recommendations'
    )
    action_type = models.CharField(max_length=15, choices=ActionType.choices)
    urgency = models.CharField(max_length=15, choices=Urgency.choices)
    description = models.TextField()
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2)
    risk_if_delayed = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} - {self.urgency}"
