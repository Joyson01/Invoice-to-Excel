# Invoice CRUD service
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

class InvoiceService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        
    async def get_invoice(self, invoice_id: str):
        pass
