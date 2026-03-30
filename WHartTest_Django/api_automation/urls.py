# -*- coding: utf-8 -*-
from rest_framework.routers import DefaultRouter

from .views import (
    ApiCollectionViewSet,
    ApiEnvironmentViewSet,
    ApiExecutionRecordViewSet,
    ApiRequestViewSet,
    ApiTestCaseViewSet,
)

router = DefaultRouter()
router.register("collections", ApiCollectionViewSet, basename="api-automation-collections")
router.register("requests", ApiRequestViewSet, basename="api-automation-requests")
router.register("environments", ApiEnvironmentViewSet, basename="api-automation-environments")
router.register("execution-records", ApiExecutionRecordViewSet, basename="api-automation-execution-records")
router.register("test-cases", ApiTestCaseViewSet, basename="api-automation-test-cases")

urlpatterns = router.urls
