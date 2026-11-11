export interface BoxItem {
  length?: number | null;
  width?: number | null;
  height?: number | null;
  weight?: number | null;
  quantity?: number | null;
}

export interface LineItem {
  description: string;
  item_code: string;
  hsn: string;
  quantity: number;
  mrp?: number | null;
}

export interface InvoiceData {
  id: string;
  filename: string;
  is_scanned: boolean;
  order_id: string;
  invoice_number: string;
  po_number: string;
  invoice_date: string;
  invoice_amount?: number | null;
  eway_bill_number: string;
  receiver_name: string;
  receiver_address: string;
  receiver_pincode: string;
  receiver_mobile: string;
  receiver_email: string;
  warehouse_name: string;
  order_description: string;
  payment_mode: string;
  cod_value?: number | null;
  insurance: string;
  invoice_url: string;
  delivery_challan: string;
  declaration: string;
  other_supporting_documents: string;
  reason: string;
  boxes: BoxItem[];
  line_items: LineItem[];
  warnings: string[];
  status: 'Ready' | 'Review Required' | 'Failed';
}

export interface ConfigData {
  apply_business_defaults: boolean;
  warehouse_name: string;
  receiver_email_default: string;
  payment_mode_default: string;
  cod_value_default: number;
  insurance_default: string;
  box_length_default: number;
  box_width_default: number;
  box_height_default: number;
  box_weight_default: number;
  default_brand: string;
}

export interface BatchSummary {
  session_id: string;
  filename: string;
  count: number;
  needs_attention: number;
}
