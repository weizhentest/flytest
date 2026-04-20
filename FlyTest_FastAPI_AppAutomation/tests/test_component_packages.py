import sqlite3
import unittest

from fastapi import HTTPException

from app.extended_routes import (
    _build_component_package_manifest,
    _install_component_package,
    _parse_component_package_manifest,
    _sanitize_package_filename,
)


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            schema_json TEXT NOT NULL DEFAULT '{}',
            default_config TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE custom_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            schema_json TEXT NOT NULL DEFAULT '{}',
            default_config TEXT NOT NULL DEFAULT '{}',
            steps_json TEXT NOT NULL DEFAULT '[]',
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE component_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            author TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'upload',
            manifest_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    return conn


class ComponentPackageTests(unittest.TestCase):
    def test_parse_json_manifest_and_sanitize_filename(self):
        manifest = _parse_component_package_manifest(
            "demo.json",
            b'{"name":"demo pack","components":[{"name":"Click","type":"touch"}]}',
        )

        self.assertEqual(manifest["name"], "demo pack")
        self.assertEqual(_sanitize_package_filename("demo pack", "json"), "demo-pack.json")

    def test_install_and_export_component_package(self):
        conn = make_conn()
        result = _install_component_package(
            conn,
            {
                "name": "demo-pack",
                "version": "1.0.0",
                "description": "test package",
                "author": "tester",
                "components": [
                    {
                        "name": "点击元素",
                        "type": "touch",
                        "category": "interaction",
                        "description": "点击动作",
                        "schema": {"selector": "string"},
                        "default_config": {"selector_type": "element"},
                        "enabled": True,
                        "sort_order": 1,
                    }
                ],
                "custom_components": [
                    {
                        "name": "登录流程",
                        "type": "login_flow_component",
                        "description": "公共登录流程",
                        "schema": {},
                        "default_config": {},
                        "steps": [{"name": "点击元素", "type": "touch", "config": {"selector_type": "element", "selector": "登录按钮"}}],
                        "enabled": True,
                        "sort_order": 2,
                    }
                ],
            },
            overwrite=True,
            source="upload",
        )

        self.assertEqual(result["counts"]["base_created"], 1)
        self.assertEqual(result["counts"]["custom_created"], 1)

        manifest = _build_component_package_manifest(
            conn,
            include_disabled=False,
            name="export-pack",
            version="2026.04.07",
            author="tester",
            description="exported",
        )
        self.assertEqual(manifest["name"], "export-pack")
        self.assertEqual(len(manifest["components"]), 1)
        self.assertEqual(len(manifest["custom_components"]), 1)
        self.assertEqual(manifest["custom_components"][0]["type"], "login_flow_component")

    def test_install_component_package_rejects_recursive_custom_components(self):
        conn = make_conn()

        with self.assertRaises(HTTPException) as context:
            _install_component_package(
                conn,
                {
                    "name": "bad-pack",
                    "version": "1.0.0",
                    "custom_components": [
                        {
                            "name": "Nested Flow",
                            "type": "nested_flow_component",
                            "description": "invalid recursive component",
                            "schema": {},
                            "default_config": {},
                            "steps": [
                                {
                                    "name": "call nested component",
                                    "kind": "custom",
                                    "type": "nested_flow_component",
                                    "component_type": "nested_flow_component",
                                    "config": {},
                                }
                            ],
                            "enabled": True,
                            "sort_order": 1,
                        }
                    ],
                },
                overwrite=True,
                source="upload",
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("nested custom components", str(context.exception.detail))

    def test_install_component_package_rejects_nested_references_between_new_custom_components(self):
        conn = make_conn()

        with self.assertRaises(HTTPException) as context:
            _install_component_package(
                conn,
                {
                    "name": "bad-pack",
                    "version": "1.0.0",
                    "custom_components": [
                        {
                            "name": "Flow A",
                            "type": "flow_a",
                            "description": "references another new custom component",
                            "schema": {},
                            "default_config": {},
                            "steps": [
                                {
                                    "name": "call flow b",
                                    "kind": "custom",
                                    "type": "flow_b",
                                    "component_type": "flow_b",
                                    "config": {},
                                }
                            ],
                            "enabled": True,
                            "sort_order": 1,
                        },
                        {
                            "name": "Flow B",
                            "type": "flow_b",
                            "description": "second custom component in same package",
                            "schema": {},
                            "default_config": {},
                            "steps": [{"name": "tap login", "type": "touch", "config": {"selector": "login"}}],
                            "enabled": True,
                            "sort_order": 2,
                        },
                    ],
                },
                overwrite=True,
                source="upload",
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("nested custom components", str(context.exception.detail))


if __name__ == "__main__":
    unittest.main()
