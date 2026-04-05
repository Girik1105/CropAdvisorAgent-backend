from django.urls import path

from .views import (
    FieldCropHealthView,
    FieldDetailView,
    FieldListCreateView,
    FieldSessionsView,
    FieldSoilProfileView,
    FieldWeatherHistoryView,
)

urlpatterns = [
    path('', FieldListCreateView.as_view(), name='field-list-create'),
    path('<uuid:field_id>/', FieldDetailView.as_view(), name='field-detail'),
    path('<uuid:field_id>/sessions/', FieldSessionsView.as_view(), name='field-sessions'),
    path('<uuid:field_id>/weather/', FieldWeatherHistoryView.as_view(), name='field-weather'),
    path('<uuid:field_id>/crop-health/', FieldCropHealthView.as_view(), name='field-crop-health'),
    path('<uuid:field_id>/soil/', FieldSoilProfileView.as_view(), name='field-soil'),
]
