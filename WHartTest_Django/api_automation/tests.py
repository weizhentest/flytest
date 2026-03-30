import json

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from projects.models import Project

from .models import ApiCollection, ApiRequest, ApiTestCase


class ApiAutomationImportDocumentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="apiadmin",
            email="apiadmin@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            name="API Automation Project",
            description="project for api automation tests",
            creator=self.user,
        )
        self.collection = ApiCollection.objects.create(
            project=self.project,
            name="Imported APIs",
            creator=self.user,
        )

    def _payload(self, response):
        if isinstance(response.data, dict) and "data" in response.data:
            return response.data["data"]
        return response.data

    def test_import_document_creates_requests_scripts_and_test_cases(self):
        openapi_document = {
            "openapi": "3.0.1",
            "info": {"title": "Demo", "version": "1.0.0"},
            "servers": [{"url": "https://example.com"}],
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "tags": ["users"],
                        "responses": {"200": {"description": "ok"}},
                    },
                    "post": {
                        "summary": "Create user",
                        "tags": ["users"],
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "example": {
                                        "name": "Alice",
                                        "email": "alice@example.com",
                                    }
                                }
                            }
                        },
                        "responses": {"201": {"description": "created"}},
                    },
                }
            },
        }

        upload = SimpleUploadedFile(
            "openapi.json",
            json.dumps(openapi_document).encode("utf-8"),
            content_type="application/json",
        )

        response = self.client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "generate_test_cases": "true",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = self._payload(response)

        self.assertEqual(payload["created_count"], 2)
        self.assertEqual(payload["generated_script_count"], 2)
        self.assertEqual(payload["created_testcase_count"], 2)
        self.assertEqual(len(payload["generated_scripts"]), 2)
        self.assertEqual(len(payload["test_cases"]), 2)
        self.assertIn("generated_script", payload["items"][0])
        self.assertEqual(ApiRequest.objects.count(), 2)
        self.assertEqual(ApiTestCase.objects.count(), 2)

        post_script = next(item["script"] for item in payload["generated_scripts"] if item["request_name"] == "Create user")
        self.assertEqual(post_script["request"]["method"], "POST")
        self.assertEqual(post_script["request"]["url"], "https://example.com/users")

    def test_import_document_can_skip_test_case_generation(self):
        markdown = b"## Login\nPOST /api/login\n```json\n{\"username\": \"demo\"}\n```"
        upload = SimpleUploadedFile("api.md", markdown, content_type="text/markdown")

        response = self.client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "generate_test_cases": "false",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = self._payload(response)

        self.assertEqual(payload["created_count"], 1)
        self.assertEqual(payload["generated_script_count"], 1)
        self.assertEqual(payload["created_testcase_count"], 0)
        self.assertEqual(ApiRequest.objects.count(), 1)
        self.assertEqual(ApiTestCase.objects.count(), 0)

    def test_test_case_list_endpoint_supports_collection_filter(self):
        request = ApiRequest.objects.create(
            collection=self.collection,
            name="List users",
            method="GET",
            url="/api/users",
            created_by=self.user,
        )
        ApiTestCase.objects.create(
            project=self.project,
            request=request,
            name="List users - Ready",
            status="ready",
            script={"request": {"method": "GET", "url": "/api/users"}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )

        response = self.client.get(
            "/api/api-automation/test-cases/",
            {
                "project": self.project.id,
                "collection": self.collection.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["collection_id"], self.collection.id)
