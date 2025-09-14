from django.urls import path
from . import views

app_name = "claims"

urlpatterns = [
    path("welcome/", views.welcome, name="welcome"),
    path("user/", views.index, name="index"),

    path("claim/<int:pk>/", views.claim_detail, name="claim_detail"),

    path("detail/<int:pk>/", views.claim_detail, name="detail"),

    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("claims/<int:pk>/flag/confirm/", views.flag_confirm, name="flag_confirm"),
    path("flag/set/<int:pk>/", views.flag_set, name="flag_set"),
    path("note/add/<int:pk>/", views.add_note, name="add_note"),
]
