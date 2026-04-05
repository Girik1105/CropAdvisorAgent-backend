from django.contrib import admin

from .models import (
    ActionRecommendation, AgentMessage, AgentSession, CropHealthRecord,
    Field, SoilProfile, WeatherSnapshot,
)

admin.site.register(Field)
admin.site.register(WeatherSnapshot)
admin.site.register(CropHealthRecord)
admin.site.register(SoilProfile)
admin.site.register(AgentSession)
admin.site.register(AgentMessage)
admin.site.register(ActionRecommendation)
