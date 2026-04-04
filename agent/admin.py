from django.contrib import admin

from .models import ActionRecommendation, AgentMessage, AgentSession, Field

admin.site.register(Field)
admin.site.register(AgentSession)
admin.site.register(AgentMessage)
admin.site.register(ActionRecommendation)
