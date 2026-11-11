from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
import uuid

class BoxItem(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    quantity: Optional[int] = None

class LineItem(BaseModel):
    description: str = ""
    item_code: str = ""
    hsn: str = ""
    quantity: int = 0
    mrp: Optional[float] = None

class InvoiceData(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    is_scanned: bool = False
    
    # Core Fields
    order_id: str = ""
    invoice_number: str = ""
    po_number: str = ""
    invoice_date: str = ""
    invoice_amount: Optional[float] = None
    eway_bill_number: str = ""
    
    # Receiver Info
    receiver_name: str = ""
    receiver_address: str = ""
    receiver_pincode: str = ""
    receiver_mobile: str = ""
    receiver_email: str = ""
    
    # Shipping / Warehouse Info
    warehouse_name: str = ""
    order_description: str = ""
    
    # Optional Fields
    payment_mode: str = ""
    cod_value: Optional[float] = None
    insurance: str = ""
    invoice_url: str = ""
    delivery_challan: str = ""
    declaration: str = ""
    other_supporting_documents: str = ""
    reason: str = ""
    
    # Structured items & boxes
    boxes: List[BoxItem] = []
    line_items: List[LineItem] = []
    
    # Validation & Status
    warnings: List[str] = []
    status: str = "Ready"  # Ready | Review Required | Failed

class InvoiceUpdate(BaseModel):
    order_id: Optional[str] = None
    invoice_number: Optional[str] = None
    po_number: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_amount: Optional[float] = None
    eway_bill_number: Optional[str] = None
    receiver_name: Optional[str] = None
    receiver_address: Optional[str] = None
    receiver_pincode: Optional[str] = None
    receiver_mobile: Optional[str] = None
    receiver_email: Optional[str] = None
    warehouse_name: Optional[str] = None
    order_description: Optional[str] = None
    payment_mode: Optional[str] = None
    cod_value: Optional[float] = None
    insurance: Optional[str] = None
    invoice_url: Optional[str] = None
    delivery_challan: Optional[str] = None
    declaration: Optional[str] = None
    other_supporting_documents: Optional[str] = None
    reason: Optional[str] = None
    boxes: Optional[List[BoxItem]] = None
    status: Optional[str] = None
