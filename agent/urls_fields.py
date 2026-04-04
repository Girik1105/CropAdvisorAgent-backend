from django.urls import path

from .views import FieldListCreateView, FieldSessionsView

urlpatterns = [
    path('', FieldListCreateView.as_view(), name='field-list-create'),
    path('<uuid:field_id>/sessions/', FieldSessionsView.as_view(), name='field-sessions'),
]
