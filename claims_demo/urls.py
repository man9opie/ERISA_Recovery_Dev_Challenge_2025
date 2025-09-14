# claims_demo/urls.py
from django.urls import path, include
from claims import views as claims_views

urlpatterns = [
    # 让根路径 / 显示 Welcome
    path("", claims_views.welcome, name="welcome_root"),

    # 其它页面都走 app 自己的 urls
    path("", include(("claims.urls", "claims"), namespace="claims")),
]
