from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.PosLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("password/change/", views.password_change, name="password_change"),
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("users/<int:user_id>/edit/", views.user_edit, name="user_edit"),
    path(
        "users/<int:user_id>/deactivate/",
        views.user_deactivate,
        name="user_deactivate",
    ),
    path(
        "users/<int:user_id>/reactivate/",
        views.user_reactivate,
        name="user_reactivate",
    ),
    path(
        "users/<int:user_id>/password/",
        views.user_password_reset,
        name="user_password_reset",
    ),
]
