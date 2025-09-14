from django.urls import path
from . import views

app_name = "claims"

urlpatterns = [
    path("welcome/", views.welcome, name="welcome"),
    path("user/", views.index, name="index"),

    # 规范的新名字
    path("claim/<int:pk>/", views.claim_detail, name="claim_detail"),

    # 兼容旧模板里用到的名字（新增这一行）
    path("detail/<int:pk>/", views.claim_detail, name="detail"),

    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("flag/confirm/<int:pk>/", views.flag_confirm, name="flag_confirm"),
    path("flag/set/<int:pk>/", views.flag_set, name="flag_set"),
    path("note/add/<int:pk>/", views.add_note, name="add_note"),
]
