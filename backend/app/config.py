import os
from pathlib import Path
from threading import Lock
from app.storage import write_json
from typing import Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    apply_business_defaults: bool = False
    # Business default values (configurable by admin)
    warehouse_name: str = "RAJPUTANA 001"
    receiver_email_default: str = ""
    payment_mode_default: str = "Prepaid"
    cod_value_default: float = Field(default=0.0, ge=0)
    insurance_default: str = "Owner Risk"
    invoice_url_default: str = ""
    delivery_challan_default: str = ""
    declaration_default: str = ""
    other_supporting_documents_default: str = ""

    # Box defaults
    box_length_default: float = Field(default=10.0, gt=0)
    box_width_default: float = Field(default=10.0, gt=0)
    box_height_default: float = Field(default=10.0, gt=0)
    box_weight_default: float = Field(default=5.0, gt=0)

    # Brand mapping for order descriptions
    brand_map: Dict[str, str] = Field(default_factory=lambda: {
        "CET": "Cetaphil",
        "CETAPHIL": "Cetaphil",
        "PHILIPS": "Philips",
        "RASHI": "Rashi",
    })
    default_brand: str = "Assorted"

CONFIG_PATH = Path(os.getenv("STATE_DIR", Path(__file__).resolve().parents[1] / "data")) / "defaults.json"
config_lock = Lock()
config = AppConfig.model_validate_json(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else AppConfig()


def get_config() -> AppConfig:
    return config


def update_config(updates: Dict[str, Any]) -> AppConfig:
    global config
    with config_lock:
        candidate = AppConfig.model_validate({**config.model_dump(), **updates})
        write_json(CONFIG_PATH, candidate.model_dump(mode="json"))
        config = candidate
        return candidate
