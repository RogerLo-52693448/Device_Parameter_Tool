import copy
import hmac
import json
import os
import secrets

from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for

from .models import calculate_project, example_project, new_id, validate_project
from .storage import load_project, save_project


def _optional_limit(value, label):
    if not value or not value.strip():
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"「{label}」必須是數字") from exc


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_path=os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir, "instance")
        ),
    )
    app.config.update(
        SECRET_KEY=os.environ.get("POWER_BUDGET_SECRET") or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        PROJECT_PATH=os.environ.get(
            "POWER_BUDGET_DATA", os.path.join(app.instance_path, "power_budget.json")
        ),
    )
    if test_config:
        app.config.update(test_config)

    @app.before_request
    def verify_csrf_token():
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            submitted = request.form.get("csrf_token", "")
            if not expected or not hmac.compare_digest(expected, submitted):
                abort(400)

    @app.context_processor
    def provide_csrf_token():
        token = session.get("csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return {"csrf_token": token}

    try:
        project = load_project(app.config["PROJECT_PATH"], example_project())
    except ValueError as exc:
        app.logger.warning("%s", exc)
        project = example_project()
    app.extensions["power_budget_project"] = project

    def persist(candidate):
        validate_project(candidate)
        save_project(app.config["PROJECT_PATH"], candidate)
        app.extensions["power_budget_project"] = candidate

    @app.get("/")
    def index():
        project = app.extensions["power_budget_project"]
        results = calculate_project(project)
        supply_rows = []
        for supply in project["supplies"]:
            supply_rows.append(
                {
                    "item": supply,
                    "load": results["supplies"][supply["id"]],
                    "capacity": _capacity(supply, results["supplies"][supply["id"]]),
                }
            )
        circuit_rows = []
        for circuit in project["circuits"]:
            circuit_rows.append(
                {
                    "item": circuit,
                    "load": results["circuits"][circuit["id"]],
                    "capacity": _capacity(circuit, results["circuits"][circuit["id"]]),
                }
            )
        devices = []
        for device in project["devices"]:
            devices.append(
                {
                    "item": device,
                    "load": results["devices"][device["id"]],
                    "circuit": next(
                        row["item"]
                        for row in circuit_rows
                        if row["item"]["id"] == device["circuit_id"]
                    ),
                }
            )
        warnings = []
        for kind, rows in (("電源", supply_rows), ("迴路", circuit_rows)):
            for row in rows:
                for metric, label in (("amps", "電流"), ("watts", "實功率")):
                    limit = row["item"].get(f"max_{metric}")
                    if limit is not None and row["load"][metric] > limit:
                        warnings.append(
                            f"{kind}「{row['item']['name']}」{label}超出上限 "
                            f"{row['load'][metric]:.2f} / {limit:g}"
                            f"{' A' if metric == 'amps' else ' W'}"
                        )
        return render_template(
            "index.html",
            project=project,
            supply_rows=supply_rows,
            circuit_rows=circuit_rows,
            devices=devices,
            warnings=warnings,
        )

    @app.post("/supplies")
    def add_supply():
        try:
            candidate = copy.deepcopy(app.extensions["power_budget_project"])
            candidate["supplies"].append(
                {
                    "id": new_id(),
                    "name": request.form.get("name", "").strip(),
                    "kind": request.form.get("kind"),
                    "voltage": float(request.form.get("voltage", "")),
                    "max_amps": _optional_limit(request.form.get("max_amps", ""), "電流上限"),
                    "max_watts": _optional_limit(request.form.get("max_watts", ""), "功率上限"),
                }
            )
            persist(candidate)
            flash("電源已新增。", "success")
        except (TypeError, ValueError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("index"))

    @app.post("/circuits")
    def add_circuit():
        try:
            candidate = copy.deepcopy(app.extensions["power_budget_project"])
            candidate["circuits"].append(
                {
                    "id": new_id(),
                    "name": request.form.get("name", "").strip(),
                    "supply_id": request.form.get("supply_id", ""),
                    "kind": request.form.get("kind"),
                    "voltage": float(request.form.get("voltage", "")),
                    "max_amps": _optional_limit(request.form.get("max_amps", ""), "電流上限"),
                    "max_watts": _optional_limit(request.form.get("max_watts", ""), "功率上限"),
                }
            )
            persist(candidate)
            flash("迴路已新增。", "success")
        except (TypeError, ValueError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("index"))

    @app.post("/devices")
    def add_device():
        try:
            candidate = copy.deepcopy(app.extensions["power_budget_project"])
            candidate["devices"].append(
                {
                    "id": new_id(),
                    "name": request.form.get("name", "").strip(),
                    "circuit_id": request.form.get("circuit_id", ""),
                    "kind": request.form.get("kind"),
                    "voltage": float(request.form.get("voltage", "")),
                    "quantity": int(request.form.get("quantity", "")),
                    "rating_type": request.form.get("rating_type"),
                    "rating": float(request.form.get("rating", "")),
                    "power_factor": float(request.form.get("power_factor", "1")),
                }
            )
            persist(candidate)
            flash("設備已新增。", "success")
        except (TypeError, ValueError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("index"))

    @app.post("/delete/<collection>/<item_id>")
    def delete_item(collection, item_id):
        if collection not in ("supplies", "circuits", "devices"):
            return "找不到項目", 404
        candidate = copy.deepcopy(app.extensions["power_budget_project"])
        items = candidate[collection]
        if collection == "supplies":
            circuit_ids = {
                circuit["id"]
                for circuit in candidate["circuits"]
                if circuit["supply_id"] == item_id
            }
            candidate["circuits"] = [
                circuit for circuit in candidate["circuits"] if circuit["id"] not in circuit_ids
            ]
            candidate["devices"] = [
                device
                for device in candidate["devices"]
                if device["circuit_id"] not in circuit_ids
            ]
        elif collection == "circuits":
            candidate["devices"] = [
                device for device in candidate["devices"] if device["circuit_id"] != item_id
            ]
        items = candidate[collection]
        remaining = [item for item in items if item["id"] != item_id]
        if len(remaining) == len(items):
            flash("找不到要刪除的項目。", "error")
        else:
            candidate[collection] = remaining
            try:
                persist(candidate)
                flash("項目已刪除。", "success")
            except ValueError as exc:
                flash(str(exc), "error")
        return redirect(url_for("index"))

    @app.post("/update/<collection>/<item_id>")
    def update_item(collection, item_id):
        if collection not in ("supplies", "circuits", "devices"):
            return "找不到項目", 404
        candidate = copy.deepcopy(app.extensions["power_budget_project"])
        item = next(
            (entry for entry in candidate[collection] if entry["id"] == item_id), None
        )
        if item is None:
            flash("找不到要編輯的項目。", "error")
            return redirect(url_for("index"))
        try:
            item["name"] = request.form.get("name", "").strip()
            if collection in ("supplies", "circuits"):
                item.update(
                    kind=request.form.get("kind"),
                    voltage=float(request.form.get("voltage", "")),
                    max_amps=_optional_limit(request.form.get("max_amps", ""), "電流上限"),
                    max_watts=_optional_limit(request.form.get("max_watts", ""), "功率上限"),
                )
            if collection == "circuits":
                item["supply_id"] = request.form.get("supply_id", "")
            elif collection == "devices":
                item.update(
                    circuit_id=request.form.get("circuit_id", ""),
                    kind=request.form.get("kind"),
                    voltage=float(request.form.get("voltage", "")),
                    quantity=int(request.form.get("quantity", "")),
                    rating_type=request.form.get("rating_type"),
                    rating=float(request.form.get("rating", "")),
                    power_factor=float(request.form.get("power_factor", "1")),
                )
            persist(candidate)
            flash("設定已更新。", "success")
        except (TypeError, ValueError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("index"))

    @app.post("/import")
    def import_project():
        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            flash("請選擇 JSON 設定檔。", "error")
            return redirect(url_for("index"))
        try:
            candidate = validate_project(json.loads(uploaded.read().decode("utf-8")))
            persist(candidate)
            flash("JSON 設定已匯入並儲存。", "success")
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            flash(f"匯入失敗：{exc}", "error")
        return redirect(url_for("index"))

    @app.get("/export")
    def export_project():
        project_json = json.dumps(
            app.extensions["power_budget_project"],
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ) + "\n"
        from io import BytesIO

        return send_file(
            BytesIO(project_json.encode("utf-8")),
            mimetype="application/json; charset=utf-8",
            as_attachment=True,
            download_name="電力計算.json",
        )

    return app


def _capacity(item, load):
    values = {}
    for metric in ("amps", "watts"):
        limit = item.get(f"max_{metric}")
        used = load[metric]
        values[metric] = {
            "limit": limit,
            "percent": used / limit * 100 if limit is not None else None,
            "remaining": limit - used if limit is not None else None,
        }
    return values
