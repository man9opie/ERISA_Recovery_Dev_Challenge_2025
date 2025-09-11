# claims/urls.py
# claims/urls.py
from django.urls import path
from . import views

app_name = "claims"  # ← 新增/确认

urlpatterns = [
    path("", views.index, name="index"),
    path("claims/<int:pk>/", views.claim_detail, name="detail"),
    path("claims/<int:pk>/notes/add/", views.add_note, name="add_note"),
    path("claims/<int:pk>/flag/confirm/", views.flag_confirm, name="flag_confirm"),
    path("claims/<int:pk>/flag/set/", views.flag_set, name="flag_set"),
]
