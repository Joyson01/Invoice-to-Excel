import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    import app.main as main
    import app.config as config_module

    monkeypatch.setattr(main, 'UPLOAD_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setattr(main, 'OUTPUT_DIR', str(tmp_path / 'output'))
    monkeypatch.setattr(main, 'SESSIONS', {})
    monkeypatch.setattr(config_module, 'config', config_module.AppConfig())
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "defaults.json")
