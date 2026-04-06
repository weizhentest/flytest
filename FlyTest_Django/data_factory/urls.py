from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DataFactoryExecuteApiView,
    DataFactoryRecordViewSet,
    DataFactoryReferencesApiView,
    DataFactoryStatisticsApiView,
    DataFactoryTagViewSet,
    ToolCatalogApiView,
    ToolScenariosApiView,
)

router = DefaultRouter()
router.register("tags", DataFactoryTagViewSet, basename="data-factory-tags")
router.register("records", DataFactoryRecordViewSet, basename="data-factory-records")

urlpatterns = router.urls + [
    path("catalog/", ToolCatalogApiView.as_view(), name="data-factory-catalog"),
    path("scenarios/", ToolScenariosApiView.as_view(), name="data-factory-scenarios"),
    path("execute/", DataFactoryExecuteApiView.as_view(), name="data-factory-execute"),
    path("statistics/", DataFactoryStatisticsApiView.as_view(), name="data-factory-statistics"),
    path("references/", DataFactoryReferencesApiView.as_view(), name="data-factory-references"),
]
