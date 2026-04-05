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


class WeatherSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='weather_snapshots')
    session = models.ForeignKey('AgentSession', on_delete=models.CASCADE, related_name='weather_snapshots', null=True, blank=True)
    temp_f = models.FloatField()
    temp_c = models.FloatField()
    humidity_pct = models.FloatField()
    wind_mph = models.FloatField()
    conditions = models.CharField(max_length=255)
    uv_index = models.FloatField(null=True, blank=True)
    precipitation_forecast = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Weather for {self.field.name} at {self.created_at}"


class CropHealthRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='crop_health_records')
    ndvi_score = models.FloatField()
    stress_level = models.CharField(max_length=20)
    vegetation_trend = models.CharField(max_length=50)
    vegetation_fraction = models.FloatField()
    last_satellite_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"NDVI {self.ndvi_score} for {self.field.name}"


class SoilProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field = models.OneToOneField(Field, on_delete=models.CASCADE, related_name='soil_profile')
    soil_type = models.CharField(max_length=100)
    ph = models.FloatField()
    organic_matter_pct = models.FloatField()
    drainage_class = models.CharField(max_length=50)
    water_holding_capacity = models.CharField(max_length=50)
    available_water_in_per_ft = models.FloatField()
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Soil: {self.soil_type} for {self.field.name}"


class MarketSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='market_snapshots')
    session = models.ForeignKey('AgentSession', on_delete=models.CASCADE, related_name='market_snapshots', null=True, blank=True)
    crop_type = models.CharField(max_length=100)
    price_per_unit = models.FloatField()
    unit = models.CharField(max_length=20)
    trend_30d = models.CharField(max_length=50)
    seasonal_outlook = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Market {self.crop_type} @ ${self.price_per_unit}/{self.unit}"


class PestRiskAssessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='pest_assessments')
    session = models.ForeignKey('AgentSession', on_delete=models.CASCADE, related_name='pest_assessments', null=True, blank=True)
    risk_level = models.CharField(max_length=20)
    primary_threats = models.JSONField(default=list)
    preventive_actions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Pest risk: {self.risk_level} for {self.field.name}"


class WaterUsageEstimate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='water_estimates')
    session = models.ForeignKey('AgentSession', on_delete=models.CASCADE, related_name='water_estimates', null=True, blank=True)
    daily_need_gal = models.IntegerField()
    deficit_pct = models.IntegerField()
    recommendation = models.TextField()
    est_cost = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Water: {self.daily_need_gal} gal/day for {self.field.name}"


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
        FIELD_AGENT = 'field_agent', 'Field Agent'
        ORCHESTRATOR = 'orchestrator', 'Orchestrator'
        RECOMMENDER = 'recommender', 'Recommender'
        FINAL_RESPONSE = 'final_response', 'Final Response'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        AgentSession, on_delete=models.CASCADE, related_name='messages'
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    tool_name = models.CharField(max_length=100, blank=True, null=True)
    tool_input = models.JSONField(blank=True, null=True)
    tool_output = models.JSONField(blank=True, null=True)
    duration_ms = models.IntegerField(blank=True, null=True)
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
    cost_breakdown = models.TextField(blank=True, default='')
    risk_if_delayed = models.TextField()
    timing_rationale = models.TextField(blank=True, default='')
    implementation_steps = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} - {self.urgency}"
