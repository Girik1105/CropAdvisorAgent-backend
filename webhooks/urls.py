from django.urls import path

from .views import SmsWebhookView

urlpatterns = [
    path('sms/', SmsWebhookView.as_view(), name='sms-webhook'),
]
