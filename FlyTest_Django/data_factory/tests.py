from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project

from .catalog import TOOLS
from .executor import TOOL_HANDLERS
from .executor import execute_tool
from .models import DataFactoryRecord


class DataFactoryApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="data_factory_admin",
            email="data_factory@example.com",
            password="password123",
        )
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(
            name="Data Factory Project",
            description="test project",
            creator=self.user,
        )

    def unwrap(self, response):
        payload = response.data
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def test_execute_endpoint_creates_record_and_tag(self):
        response = self.client.post(
            reverse("data-factory-execute"),
            {
                "project": self.project.id,
                "tool_name": "random_string",
                "input_data": {
                    "length": 8,
                    "count": 1,
                    "char_type": "alphanumeric",
                },
                "save_record": True,
                "tag_names": ["登录账号"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.unwrap(response)
        self.assertTrue(data["saved"])
        self.assertEqual(DataFactoryRecord.objects.count(), 1)
        record = DataFactoryRecord.objects.prefetch_related("tags").get()
        self.assertEqual(record.tool_name, "random_string")
        self.assertEqual(record.tags.count(), 1)
        self.assertEqual(data["record"]["reference_placeholder_api"], f"{{{{df.record.{record.id}}}}}")
        self.assertEqual(data["record"]["reference_placeholder_ui"], "$" + f"{{{{df.record.{record.id}}}}}")

    def test_references_endpoint_returns_api_and_ui_placeholders(self):
        record = DataFactoryRecord.objects.create(
            project=self.project,
            creator=self.user,
            tool_name="random_integer",
            tool_category="random",
            tool_scenario="data_generation",
            input_data={"min_value": 1, "max_value": 9, "count": 1},
            output_data={"success": True, "tool_name": "random_integer", "result": 7, "summary": "ok", "metadata": {}},
            is_saved=True,
        )
        tag = self.project.data_factory_tags.create(name="订单号", code="订单号", creator=self.user)
        record.tags.add(tag)

        api_response = self.client.get(
            reverse("data-factory-references"),
            {"project": self.project.id, "mode": "api"},
        )
        ui_response = self.client.get(
            reverse("data-factory-references"),
            {"project": self.project.id, "mode": "ui"},
        )

        self.assertEqual(api_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ui_response.status_code, status.HTTP_200_OK)

        api_data = self.unwrap(api_response)
        ui_data = self.unwrap(ui_response)

        self.assertEqual(api_data["tags"][0]["placeholder"], "{{df.tag.订单号}}")
        self.assertEqual(api_data["records"][0]["placeholder"], f"{{{{df.record.{record.id}}}}}")
        self.assertEqual(ui_data["tags"][0]["placeholder"], "${{df.tag.订单号}}")
        self.assertEqual(ui_data["records"][0]["placeholder"], "$" + f"{{{{df.record.{record.id}}}}}")

    def test_records_endpoint_filters_by_category_and_saved_state(self):
        DataFactoryRecord.objects.create(
            project=self.project,
            creator=self.user,
            tool_name="random_uuid",
            tool_category="random",
            tool_scenario="data_generation",
            input_data={"count": 1},
            output_data={"success": True, "tool_name": "random_uuid", "result": "uuid", "summary": "ok", "metadata": {}},
            is_saved=True,
        )
        DataFactoryRecord.objects.create(
            project=self.project,
            creator=self.user,
            tool_name="json_validate",
            tool_category="json",
            tool_scenario="data_validation",
            input_data={"text": "{}"},
            output_data={"success": True, "tool_name": "json_validate", "result": {"valid": True}, "summary": "ok", "metadata": {}},
            is_saved=False,
        )

        response = self.client.get(
            reverse("data-factory-records-list"),
            {
                "project": self.project.id,
                "tool_category": "random",
                "is_saved": "true",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.unwrap(response)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["tool_name"], "random_uuid")


class DataFactoryExecutorTests(APITestCase):
    def test_execute_tool_supports_json_tree_result(self):
        result = execute_tool(
            "json_format",
            {
                "text": '{"name":"FlyTest","features":["api","ui"]}',
                "indent": 2,
                "sort_keys": False,
            },
        )

        self.assertEqual(result["tool_name"], "json_format")
        self.assertIn('"FlyTest"', result["result"]["text"])
        self.assertEqual(result["result"]["parsed"]["name"], "FlyTest")
        self.assertEqual(result["result"]["parsed"]["features"][1], "ui")

    def test_all_catalog_tools_have_executor_handlers(self):
        catalog_tool_names = {tool["name"] for tool in TOOLS}
        handler_tool_names = set(TOOL_HANDLERS.keys())

        missing_handlers = sorted(catalog_tool_names - handler_tool_names)
        orphan_handlers = sorted(handler_tool_names - catalog_tool_names)

        self.assertEqual(missing_handlers, [], f"缺少 handler 的工具: {missing_handlers}")
        self.assertEqual(orphan_handlers, [], f"catalog 中不存在但注册了 handler 的工具: {orphan_handlers}")
