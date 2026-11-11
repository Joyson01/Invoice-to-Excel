from fastapi import APIRouter
from app.models.schemas import ConfigResponse, ConfigUpdate
from app.config import settings

router = APIRouter()

@router.get("/config")
async def get_config():
    return {}

@router.patch("/config")
async def update_config(data: ConfigUpdate):
    return {}
