import sys
from pathlib import Path

from django.test import SimpleTestCase


ACTUATOR_PATH = Path(__file__).resolve().parents[2] / "FlyTest_Actuator"
if str(ACTUATOR_PATH) not in sys.path:
    sys.path.insert(0, str(ACTUATOR_PATH))

from data_processor import DataProcessor  # noqa: E402


class UiAutomationDataFactoryReferenceTests(SimpleTestCase):
    def test_data_processor_resolves_nested_data_factory_variables(self):
        processor = DataProcessor()
        processor.set_cache(
            "df",
            {
                "tag": {
                    "login_name": "tester01",
                    "profile": {"name": "FlyTest", "roles": ["admin", "qa"]},
                },
                "record": {
                    "12": {"token": "abc123", "enabled": True},
                },
            },
        )

        resolved = processor.replace(
            {
                "username": "${{df.tag.login_name}}",
                "summary": "当前用户：${{df.tag.profile.name}}",
                "token": "${{df.record.12.token}}",
                "enabled": "${{df.record.12.enabled}}",
            }
        )

        self.assertEqual(resolved["username"], "tester01")
        self.assertEqual(resolved["summary"], "当前用户：FlyTest")
        self.assertEqual(resolved["token"], "abc123")
        self.assertIs(resolved["enabled"], True)

    def test_data_processor_preserves_native_type_for_whole_placeholder(self):
        processor = DataProcessor()
        processor.set_cache(
            "df",
            {
                "record": {
                    "88": {"items": ["A", "B"], "meta": {"count": 2}},
                }
            },
        )

        resolved = processor.replace("${{df.record.88}}")

        self.assertEqual(resolved, {"items": ["A", "B"], "meta": {"count": 2}})
