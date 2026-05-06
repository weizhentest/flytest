from django.db.models import Count, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SiteNotificationRecipient, SiteNotificationReply
from .serializers import (
    SiteNotificationCreateResponseSerializer,
    SiteNotificationCreateSerializer,
    SiteNotificationDetailSerializer,
    SiteNotificationRecipientSerializer,
    SiteNotificationReplyCreateSerializer,
    SiteNotificationReplySerializer,
)


class SiteNotificationCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"detail": "只有管理员可以发送站内通知。"}, status=status.HTTP_403_FORBIDDEN)

        serializer = SiteNotificationCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        notification = serializer.save()
        response_serializer = SiteNotificationCreateResponseSerializer(notification)
        return Response(
            {
                "message": f"通知发送成功，已通知 {notification.recipient_count} 人。",
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class SiteNotificationInboxAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_only = str(request.query_params.get("unread_only", "")).lower() in {"1", "true", "yes"}
        limit = request.query_params.get("limit")
        queryset = SiteNotificationRecipient.objects.select_related(
            "notification",
            "notification__sender",
            "notification__project",
        ).filter(user=request.user)

        if unread_only:
            queryset = queryset.filter(is_read=False)

        queryset = queryset.order_by("is_read", "-notification__created_at", "-id")
        if limit:
            try:
                queryset = queryset[: max(1, min(int(limit), 100))]
            except (TypeError, ValueError):
                queryset = queryset[:20]

        serializer = SiteNotificationRecipientSerializer(queryset, many=True)
        return Response(
            {
                "items": serializer.data,
                "unread_count": SiteNotificationRecipient.objects.filter(user=request.user, is_read=False).count(),
            }
        )


class SiteNotificationUnreadCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        counters = SiteNotificationRecipient.objects.filter(user=request.user).aggregate(
            unread_count=Count("id", filter=Q(is_read=False)),
            total_count=Count("id"),
        )
        return Response(counters)


class SiteNotificationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        recipient = SiteNotificationRecipient.objects.select_related(
            "notification",
            "notification__sender",
            "notification__project",
        ).prefetch_related(
            "notification__replies",
            "notification__replies__sender",
        ).filter(user=request.user, pk=pk).first()
        if recipient is None:
            return Response({"detail": "通知不存在或已被移除。"}, status=status.HTTP_404_NOT_FOUND)
        serializer = SiteNotificationDetailSerializer(recipient)
        return Response(serializer.data)


class SiteNotificationMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        recipient = SiteNotificationRecipient.objects.filter(user=request.user, pk=pk).first()
        if recipient is None:
            return Response({"detail": "通知不存在或已被移除。"}, status=status.HTTP_404_NOT_FOUND)

        changed = recipient.mark_as_read()
        unread_count = SiteNotificationRecipient.objects.filter(user=request.user, is_read=False).count()
        return Response(
            {
                "message": "消息已标记为已读。" if changed else "该消息已是已读状态。",
                "data": {
                    "id": recipient.id,
                    "is_read": recipient.is_read,
                    "read_at": recipient.read_at,
                    "unread_count": unread_count,
                },
            }
        )


class SiteNotificationReplyListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_recipient(self, request, pk):
        return SiteNotificationRecipient.objects.select_related(
            "notification",
            "notification__sender",
            "notification__project",
        ).filter(user=request.user, pk=pk).first()

    def get(self, request, pk):
        recipient = self._get_recipient(request, pk)
        if recipient is None:
            return Response({"detail": "通知不存在或已被移除。"}, status=status.HTTP_404_NOT_FOUND)

        queryset = recipient.notification.replies.select_related("sender").order_by("created_at", "id")
        serializer = SiteNotificationReplySerializer(queryset, many=True)
        return Response({"items": serializer.data})

    def post(self, request, pk):
        recipient = self._get_recipient(request, pk)
        if recipient is None:
            return Response({"detail": "通知不存在或已被移除。"}, status=status.HTTP_404_NOT_FOUND)

        serializer = SiteNotificationReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reply = SiteNotificationReply.objects.create(
            notification=recipient.notification,
            sender=request.user,
            content=serializer.validated_data["content"],
        )
        response_serializer = SiteNotificationReplySerializer(reply)
        return Response(
            {
                "message": "回复发送成功。",
                "data": response_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
