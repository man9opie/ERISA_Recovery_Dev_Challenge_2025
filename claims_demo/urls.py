# claims_demo/urls.py
from django.urls import path, include
from claims import views as claims_views

urlpatterns = [
    path("", claims_views.welcome, name="welcome_root"),

    path("", include(("claims.urls", "claims"), namespace="claims")),
]
