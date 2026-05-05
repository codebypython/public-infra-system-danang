from app.utils.codes import asset_code, report_code, task_code


def test_asset_code_format():
    assert asset_code("HC", "lamp", 7) == "DN-HC-LAMP-0007"
    assert asset_code("ST", "ev_charging", 99) == "DN-ST-EV-0099"


def test_report_task_codes():
    assert report_code(1, year=2026) == "RPT-2026-000001"
    assert task_code(123, year=2026) == "TASK-2026-000123"
