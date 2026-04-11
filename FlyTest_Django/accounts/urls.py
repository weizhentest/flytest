from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangeCurrentUserPasswordAPIView,
    ContentTypeViewSet,
    CurrentUserAPIView,
    CurrentUserProfileAPIView,
    GroupViewSet,
    LogoutAPIView,
    PermissionViewSet,
    UserCreateAPIView,
    UserViewSet,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"groups", GroupViewSet, basename="group")
router.register(r"permissions", PermissionViewSet, basename="permission")
router.register(r"content-types", ContentTypeViewSet, basename="content-type")

urlpatterns = [
    path("", include(router.urls)),
    path("register/", UserCreateAPIView.as_view(), name="user-register"),
    path("me/", CurrentUserAPIView.as_view(), name="user-me"),
    path("profile/", CurrentUserProfileAPIView.as_view(), name="user-profile"),
    path(
        "change-password/",
        ChangeCurrentUserPasswordAPIView.as_view(),
        name="user-change-password",
    ),
    path("logout/", LogoutAPIView.as_view(), name="user-logout"),
]
