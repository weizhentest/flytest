from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ImportExportTemplateViewSet

app_name = 'testcase_templates'

router = DefaultRouter()
router.register(r'testcase-templates', ImportExportTemplateViewSet, basename='testcase-template')

urlpatterns = [
    path('', include(router.urls)),
]
