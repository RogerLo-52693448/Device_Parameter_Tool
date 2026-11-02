import math
from uuid import uuid4

SCHEMA_VERSION = 1


def new_id():
    return uuid4().hex


def example_project():
    supply_ac = new_id()
    circuit_ac = new_id()
    return {
        "schema_version": SCHEMA_VERSION,
        "supplies": [
            {
                "id": supply_ac,
                "name": "110 V 電源",
                "kind": "AC",
                "voltage": 110,
                "output_min_voltage": None,
                "output_max_voltage": None,
                "max_amps": None,
                "max_watts": None,
            },
        ],
        "circuits": [
            {
                "id": circuit_ac,
                "name": "110 V 迴路",
                "supply_id": supply_ac,
                "kind": "AC",
                "voltage": 110,
                "max_amps": None,
                "max_watts": None,
            },
        ],
        "devices": [
            {
                "id": new_id(),
                "name": "設備 1",
                "circuit_id": circuit_ac,
                "kind": "AC",
                "voltage": 110,
                "quantity": 2,
                "rating_type": "voltage_current",
                "rating": 1,
                "power_factor": 1,
            },
        ],
    }


def _number(value, label, *, positive=False):
    if isinstance(value, bool):
        raise ValueError(f"「{label}」必須是有限數值")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"「{label}」必須是有限數值") from exc
    if not math.isfinite(result) or (result <= 0 if positive else result < 0):
        condition = "大於 0" if positive else "不可為負數"
        raise ValueError(f"「{label}」{condition}")
    return result


def _required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"「{label}」不可空白")
    return value.strip()


def validate_project(project):
    if (
        not isinstance(project, dict)
        or type(project.get("schema_version")) is not int
        or project["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError("不支援的 JSON 格式版本")

    for key in ("supplies", "circuits", "devices"):
        if not isinstance(project.get(key), list):
            raise ValueError(f"{key} 必須是清單")

    ids = set()
    for collection in ("supplies", "circuits", "devices"):
        for item in project[collection]:
            if not isinstance(item, dict):
                raise ValueError("設定項目格式錯誤")
            item_id = _required_text(item.get("id"), "識別碼")
            if item_id in ids:
                raise ValueError("識別碼不可重複")
            ids.add(item_id)
            _required_text(item.get("name"), "名稱")

    supplies = {item["id"]: item for item in project["supplies"]}
    circuits = {item["id"]: item for item in project["circuits"]}
    for supply in project["supplies"]:
        if supply.get("kind") not in ("AC", "DC"):
            raise ValueError("電源類型必須是 AC 或 DC")
        _number(supply.get("voltage"), "電源電壓", positive=True)
        output_min = supply.get("output_min_voltage")
        output_max = supply.get("output_max_voltage")
        if (output_min is None) != (output_max is None):
            raise ValueError("轉換輸出電壓範圍必須同時設定最低與最高電壓")
        if output_min is not None:
            if supply["kind"] != "AC":
                raise ValueError("只有 AC 電源可設定轉換輸出電壓")
            output_min = _number(output_min, "轉換輸出最低電壓", positive=True)
            output_max = _number(output_max, "轉換輸出最高電壓", positive=True)
            if output_min > output_max:
                raise ValueError("轉換輸出最低電壓不可高於最高電壓")
            if supply.get("max_amps") is not None:
                raise ValueError("轉換前的 380 V 電流需由廠商確認，請改以瓦數設定電源上限")
        for limit in ("max_amps", "max_watts"):
            if supply.get(limit) is not None:
                _number(supply[limit], "電源容量上限", positive=True)

    for circuit in project["circuits"]:
        if circuit.get("kind") not in ("AC", "DC"):
            raise ValueError("迴路類型必須是 AC 或 DC")
        voltage = _number(circuit.get("voltage"), "迴路電壓", positive=True)
        supply = supplies.get(circuit.get("supply_id"))
        if supply is None:
            raise ValueError("迴路必須連接至現有電源")
        if circuit["kind"] != supply["kind"]:
            raise ValueError("迴路類型必須符合所連接的電源")
        output_min = supply.get("output_min_voltage")
        output_max = supply.get("output_max_voltage")
        if output_min is not None:
            if not float(output_min) <= voltage <= float(output_max):
                raise ValueError("迴路電壓必須位於電源的轉換輸出電壓範圍內")
        elif voltage != float(supply["voltage"]):
            raise ValueError("迴路電壓必須符合所連接的電源")
        for limit in ("max_amps", "max_watts"):
            if circuit.get(limit) is not None:
                _number(circuit[limit], "迴路容量上限", positive=True)

    for device in project["devices"]:
        circuit = circuits.get(device.get("circuit_id"))
        if circuit is None:
            raise ValueError("設備必須連接至現有迴路")
        if device.get("kind") not in ("AC", "DC"):
            raise ValueError("設備類型必須是 AC 或 DC")
        if device["kind"] != circuit["kind"]:
            raise ValueError("設備類型必須符合所連接的迴路")
        voltage = _number(device.get("voltage"), "設備電壓", positive=True)
        if voltage != float(circuit["voltage"]):
            raise ValueError("設備電壓必須符合所連接的迴路")
        quantity = device.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("設備數量必須是正整數")
        if device.get("rating_type") not in ("watts", "amps", "voltage_current"):
            raise ValueError("設備額定值必須是瓦特、安培或電壓與安培")
        _number(device.get("rating"), "設備額定值")
        if device["kind"] == "AC" and device["rating_type"] != "voltage_current":
            power_factor = _number(device.get("power_factor"), "功率因數", positive=True)
            if power_factor > 1:
                raise ValueError("功率因數必須大於 0 且不大於 1")

    return project


def device_load(device):
    voltage = float(device["voltage"])
    rating = float(device["rating"]) * device["quantity"]
    if device["kind"] == "DC":
        watts = rating if device["rating_type"] == "watts" else voltage * rating
        amps = watts / voltage
        return {"watts": watts, "amps": amps, "va": None}

    if device["rating_type"] == "voltage_current":
        amps = rating
        va = voltage * amps
        return {"watts": va, "amps": amps, "va": va}

    power_factor = float(device["power_factor"])
    if device["rating_type"] == "watts":
        watts = rating
        va = watts / power_factor
        amps = va / voltage
    else:
        amps = rating
        va = voltage * amps
        watts = va * power_factor
    return {"watts": watts, "amps": amps, "va": va}


def calculate_project(project):
    validate_project(project)
    circuit_by_id = {circuit["id"]: circuit for circuit in project["circuits"]}
    supplies_by_id = {supply["id"]: supply for supply in project["supplies"]}
    circuit_loads = {
        circuit["id"]: {"watts": 0.0, "amps": 0.0, "va": 0.0}
        for circuit in project["circuits"]
    }
    device_results = {}
    for device in project["devices"]:
        load = device_load(device)
        target = circuit_loads[device["circuit_id"]]
        for metric in ("watts", "amps"):
            target[metric] += load[metric]
        if load["va"] is not None:
            target["va"] += load["va"]
        device_results[device["id"]] = load

    supply_loads = {
        supply["id"]: {"watts": 0.0, "amps": 0.0, "va": 0.0}
        for supply in project["supplies"]
    }
    for circuit in project["circuits"]:
        source = supply_loads[circuit["supply_id"]]
        load = circuit_loads[circuit["id"]]
        for metric in ("watts", "amps", "va"):
            source[metric] += load[metric]

    for supply in project["supplies"]:
        if supply.get("output_min_voltage") is not None:
            supply_loads[supply["id"]]["amps"] = None

    for load_group in (device_results, circuit_loads, supply_loads):
        for load in load_group.values():
            if any(value is not None and not math.isfinite(value) for value in load.values()):
                raise ValueError("計算結果超出可表示範圍")

    summary = {
        "watts": sum(load["watts"] for load in device_results.values()),
        "va": sum(load["va"] or 0 for load in device_results.values()),
        "amps": sum(load["amps"] for load in device_results.values()),
        "has_estimated_watts": any(
            device["kind"] == "AC" and device["rating_type"] == "voltage_current"
            for device in project["devices"]
        ),
        "supply_inputs": sorted(
            {
                (
                    supplies_by_id[
                        circuit_by_id[device["circuit_id"]]["supply_id"]
                    ]["kind"],
                    float(
                        supplies_by_id[
                            circuit_by_id[device["circuit_id"]]["supply_id"]
                        ]["voltage"]
                    ),
                )
                for device in project["devices"]
            }
        ),
    }

    return {
        "circuits": circuit_loads,
        "supplies": supply_loads,
        "devices": device_results,
        "summary": summary,
    }
