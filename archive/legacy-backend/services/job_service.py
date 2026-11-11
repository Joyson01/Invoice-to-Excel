# Job processing orchestration
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

class JobService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        
    async def process_job(self, job_id: str):
        pass
