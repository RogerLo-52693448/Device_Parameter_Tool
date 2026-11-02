import copy
from io import BytesIO
import json
import tempfile
import unittest
from pathlib import Path

from power_budget.models import (
    calculate_project,
    device_load,
    example_project,
    validate_project,
)
from power_budget.storage import load_project, save_project
from power_budget.web import create_app


class CalculationTests(unittest.TestCase):
    def test_dc_watt_and_amp_ratings_and_quantity(self):
        watts = {
            "kind": "DC",
            "voltage": 24,
            "rating_type": "watts",
            "rating": 12,
            "quantity": 3,
        }
        amps = {**watts, "rating_type": "amps", "rating": 0.5}
        self.assertEqual(device_load(watts), {"watts": 36.0, "amps": 1.5, "va": None})
        self.assertEqual(device_load(amps), {"watts": 36.0, "amps": 1.5, "va": None})

    def test_ac_watt_and_amp_ratings_apply_power_factor(self):
        watts = {
            "kind": "AC",
            "voltage": 120,
            "rating_type": "watts",
            "rating": 120,
            "quantity": 1,
            "power_factor": 0.8,
        }
        amps = {**watts, "rating_type": "amps", "rating": 1}
        self.assertEqual(device_load(watts), {"watts": 120.0, "amps": 1.25, "va": 150.0})
        self.assertEqual(device_load(amps), {"watts": 96.0, "amps": 1.0, "va": 120.0})

    def test_project_aggregates_at_circuit_and_supply(self):
        project = example_project()
        results = calculate_project(project)
        ac_circuit = next(item for item in project["circuits"] if item["kind"] == "AC")
        ac_supply = next(item for item in project["supplies"] if item["kind"] == "AC")
        self.assertEqual(results["circuits"][ac_circuit["id"]]["watts"], 176)
        self.assertAlmostEqual(results["circuits"][ac_circuit["id"]]["amps"], 1.6)
        self.assertEqual(results["supplies"][ac_supply["id"]]["va"], 176)
        self.assertEqual(results["summary"]["watts"], 176)
        self.assertEqual(results["summary"]["va"], 176)
        self.assertTrue(results["summary"]["has_estimated_watts"])
        self.assertIsNone(results["supplies"][ac_supply["id"]]["amps"])

    def test_device_voltage_and_current_estimate_maximum_watts_at_pf_one(self):
        device = {
            "kind": "AC",
            "voltage": 220,
            "rating_type": "voltage_current",
            "rating": 2.5,
            "quantity": 3,
        }
        self.assertEqual(
            device_load(device),
            {"watts": 1650.0, "amps": 7.5, "va": 1650.0},
        )


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.project = example_project()

    def test_rejects_mismatched_device_connection(self):
        project = copy.deepcopy(self.project)
        ac_device = next(item for item in project["devices"] if item["kind"] == "AC")
        ac_device["kind"] = "DC"
        with self.assertRaisesRegex(ValueError, "設備類型"):
            validate_project(project)

    def test_accepts_circuit_in_ac_converter_output_range(self):
        project = copy.deepcopy(self.project)
        ac_supply = next(item for item in project["supplies"] if item["kind"] == "AC")
        ac_circuit = next(item for item in project["circuits"] if item["kind"] == "AC")
        ac_supply.update(
            voltage=380,
            output_min_voltage=110,
            output_max_voltage=220,
            max_amps=None,
        )
        ac_circuit["voltage"] = 220
        ac_device = next(item for item in project["devices"] if item["kind"] == "AC")
        ac_device["voltage"] = 220
        validate_project(project)
        ac_circuit["voltage"] = 230
        with self.assertRaisesRegex(ValueError, "轉換輸出電壓範圍"):
            validate_project(project)

    def test_rejects_nonfinite_negative_and_invalid_capacity_values(self):
        for invalid in (-1, float("nan"), float("inf")):
            project = copy.deepcopy(self.project)
            project["devices"][0]["rating"] = invalid
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                validate_project(project)
        project = copy.deepcopy(self.project)
        circuit = project["circuits"][0]
        circuit["max_amps"] = 0
        with self.assertRaisesRegex(ValueError, "大於 0"):
            validate_project(project)

    def test_allows_zero_load_but_requires_positive_integer_quantity(self):
        project = copy.deepcopy(self.project)
        project["devices"][0]["rating"] = 0
        validate_project(project)
        project["devices"][0]["quantity"] = 0
        with self.assertRaisesRegex(ValueError, "正整數"):
            validate_project(project)


class StorageAndWebTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.project_path = Path(self.temp_dir.name) / "project.json"
        self.app = create_app(
            {"TESTING": True, "PROJECT_PATH": str(self.project_path), "SECRET_KEY": "test"}
        )
        self.client = self.app.test_client()
        self.client.get("/")
        with self.client.session_transaction() as session:
            self.csrf_token = session["csrf_token"]

    def test_json_storage_round_trips_traditional_chinese(self):
        project = example_project()
        project["supplies"][0]["name"] = "中文交流電源"
        save_project(self.project_path, project)
        loaded = load_project(self.project_path, {})
        self.assertEqual(loaded, project)
        self.assertIn("中文交流電源", self.project_path.read_text(encoding="utf-8"))

    def test_existing_schema_one_project_without_converter_fields_still_renders(self):
        project = example_project()
        supply = project["supplies"][0]
        supply.pop("output_min_voltage")
        supply.pop("output_max_voltage")
        supply["voltage"] = 110
        supply["max_amps"] = 15
        device = project["devices"][0]
        device.update(rating_type="watts", rating=60, power_factor=0.9)
        save_project(self.project_path, project)
        legacy_app = create_app(
            {"TESTING": True, "PROJECT_PATH": str(self.project_path), "SECRET_KEY": "test"}
        )
        response = legacy_app.test_client().get("/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_is_localized_and_shows_wiring_and_capacity(self):
        response = self.client.get("/")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("電力計算", page)
        self.assertIn("配線圖與負載", page)
        self.assertIn("工作燈", page)
        self.assertIn("剩餘", page)
        self.assertIn("設備最大功率需求估算", page)
        self.assertIn("380 V", page)
        self.assertIn("PF=1", page)

    def test_post_without_csrf_token_is_rejected(self):
        response = self.client.post("/supplies", data={"name": "未授權電源"})
        self.assertEqual(response.status_code, 400)

    def test_add_device_from_voltage_current_spec(self):
        project = self.app.extensions["power_budget_project"]
        circuit = next(item for item in project["circuits"] if item["kind"] == "AC")
        response = self.client.post(
            "/devices",
            data={
                "csrf_token": self.csrf_token,
                "name": "真空幫浦",
                "circuit_id": circuit["id"],
                "kind": "AC",
                "voltage": "110",
                "quantity": "2",
                "rating_type": "voltage_current",
                "rating": "3",
                "power_factor": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        device = self.app.extensions["power_budget_project"]["devices"][-1]
        self.assertEqual(device_load(device)["watts"], 660)

    def test_export_and_import_round_trip_json(self):
        export = self.client.get("/export")
        self.assertEqual(export.status_code, 200)
        exported = json.loads(export.get_data(as_text=True))
        exported["supplies"][0]["name"] = "匯入中文電源"
        response = self.client.post(
            "/import",
            data={
                "csrf_token": self.csrf_token,
                "file": (
                    BytesIO(json.dumps(exported, ensure_ascii=False).encode("utf-8")),
                    "project.json",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.app.extensions["power_budget_project"]["supplies"][0]["name"],
            "匯入中文電源",
        )
        self.assertEqual(load_project(self.project_path, {})["schema_version"], 1)

    def test_edit_invalid_connection_is_rejected_without_saving(self):
        project = self.app.extensions["power_budget_project"]
        device = next(item for item in project["devices"] if item["kind"] == "AC")
        response = self.client.post(
            f"/update/devices/{device['id']}",
            data={
                "name": "錯誤連接",
                "circuit_id": device["circuit_id"],
                "kind": "DC",
                "voltage": "110",
                "quantity": "1",
                "rating_type": "watts",
                "rating": "60",
                "power_factor": "0.9",
                "csrf_token": self.csrf_token,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(device["name"], "工作燈")
        self.assertFalse(self.project_path.exists())

    def test_deleting_supply_removes_its_circuits_and_devices(self):
        project = self.app.extensions["power_budget_project"]
        supply = next(item for item in project["supplies"] if item["kind"] == "AC")
        self.client.post(
            f"/delete/supplies/{supply['id']}", data={"csrf_token": self.csrf_token}
        )
        updated = self.app.extensions["power_budget_project"]
        self.assertFalse(any(item["supply_id"] == supply["id"] for item in updated["circuits"]))
        self.assertEqual(len(updated["devices"]), 0)


if __name__ == "__main__":
    unittest.main()
