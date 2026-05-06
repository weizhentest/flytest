from django.urls import path

from .views import (
    SiteNotificationCreateAPIView,
    SiteNotificationDetailAPIView,
    SiteNotificationInboxAPIView,
    SiteNotificationMarkReadAPIView,
    SiteNotificationReplyListCreateAPIView,
    SiteNotificationUnreadCountAPIView,
)


urlpatterns = [
    path("", SiteNotificationCreateAPIView.as_view(), name="site-notification-create"),
    path("inbox/", SiteNotificationInboxAPIView.as_view(), name="site-notification-inbox"),
    path("inbox/unread-count/", SiteNotificationUnreadCountAPIView.as_view(), name="site-notification-unread-count"),
    path("inbox/<int:pk>/", SiteNotificationDetailAPIView.as_view(), name="site-notification-detail"),
    path("inbox/<int:pk>/mark-read/", SiteNotificationMarkReadAPIView.as_view(), name="site-notification-mark-read"),
    path("inbox/<int:pk>/replies/", SiteNotificationReplyListCreateAPIView.as_view(), name="site-notification-replies"),
]
