import { useState } from 'react';
import { AlertCircle, AlertTriangle, Plus, Trash2, X } from 'lucide-react';
import type { InvoiceData, ConfigData, BoxItem } from '../types';

// Edit Form Modal Component
export default function InvoiceEditModal({ 
  invoice, 
  config,
  onClose, 
  onSave 
}: { 
  invoice: InvoiceData; 
  config: ConfigData | null;
  onClose: () => void; 
  onSave: (inv: InvoiceData) => void; 
}) {
  const [formData, setFormData] = useState<InvoiceData>({ ...invoice });

  const handleChange = (field: keyof InvoiceData, val: any) => {
    setFormData(prev => {
      const next = { ...prev, [field]: val };
      if (field === 'po_number') {
        next.order_id = val ? val : next.invoice_number;
      } else if (field === 'invoice_number' && !next.po_number) {
        next.order_id = val;
      }
      return next;
    });
  };

  const handleBoxChange = (idx: number, field: keyof BoxItem, val: any) => {
    const nextBoxes = [...formData.boxes];
    nextBoxes[idx] = { ...nextBoxes[idx], [field]: val === '' ? null : Number(val) };
    setFormData(prev => ({ ...prev, boxes: nextBoxes }));
  };

  const addBox = () => {
    setFormData(prev => ({
      ...prev,
      boxes: [...prev.boxes, {
        length: config?.apply_business_defaults ? config.box_length_default : null,
        width: config?.apply_business_defaults ? config.box_width_default : null,
        height: config?.apply_business_defaults ? config.box_height_default : null,
        weight: config?.apply_business_defaults ? config.box_weight_default : null,
        quantity: null
      }]
    }));
  };

  const removeBox = (idx: number) => {
    setFormData(prev => ({
      ...prev,
      boxes: prev.boxes.filter((_, i) => i !== idx)
    }));
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center">
              Edit Invoice Data
              <span className="ml-2 text-xs font-normal text-slate-500">({formData.filename})</span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">Order_ID connects Orders, Boxes, and Invoice sections</p>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {formData.warnings && formData.warnings.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl">
              <h4 className="text-xs font-semibold uppercase text-amber-800 tracking-wider flex items-center mb-1">
                <AlertTriangle className="w-4 h-4 mr-1.5 text-amber-600" />
                Validation Warnings
              </h4>
              <ul className="list-disc pl-5 text-xs text-amber-700 space-y-0.5">
                {formData.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {formData.is_scanned && (
            <div className="bg-blue-50 border border-blue-200 p-4 rounded-xl flex items-center text-sm text-blue-700">
              <AlertCircle className="w-5 h-5 text-blue-500 mr-2 flex-shrink-0" />
              Scanned / image-based invoice processed via OCR fallback.
            </div>
          )}

          {/* Section 1: Identification */}
          <div>
            <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider mb-3">Order & Invoice ID</h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Order ID <span className="text-indigo-600 text-[10px] font-normal">(Primary Key)</span>
                </label>
                <input
                  type="text"
                  value={formData.order_id}
                  onChange={(e) => handleChange('order_id', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">PO Number</label>
                <input
                  type="text"
                  value={formData.po_number}
                  onChange={(e) => handleChange('po_number', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Invoice Number</label>
                <input
                  type="text"
                  value={formData.invoice_number}
                  onChange={(e) => handleChange('invoice_number', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Financial & Shipping */}
          <div>
            <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider mb-3">Financial & Shipping</h4>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Invoice Amount (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.invoice_amount ?? ''}
                  onChange={(e) => handleChange('invoice_amount', e.target.value === '' ? null : Number(e.target.value))}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">E-Way Bill Number</label>
                <input
                  type="text"
                  value={formData.eway_bill_number}
                  onChange={(e) => handleChange('eway_bill_number', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Warehouse Name</label>
                <input
                  type="text"
                  value={formData.warehouse_name}
                  onChange={(e) => handleChange('warehouse_name', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Payment Mode</label>
                <input
                  type="text"
                  value={formData.payment_mode}
                  onChange={(e) => handleChange('payment_mode', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>
          </div>

          {/* Section 3: Receiver Information */}
          <div>
            <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider mb-3">Receiver (Consignee)</h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Receiver Name</label>
                <input
                  type="text"
                  value={formData.receiver_name}
                  onChange={(e) => handleChange('receiver_name', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Mobile (10 Digits)</label>
                <input
                  type="text"
                  value={formData.receiver_mobile}
                  onChange={(e) => handleChange('receiver_mobile', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Receiver Address <span className="text-slate-400 font-normal">(Multi-line preserved)</span>
                </label>
                <textarea
                  rows={4}
                  value={formData.receiver_address}
                  onChange={(e) => handleChange('receiver_address', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                />
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Pincode (6 Digits)</label>
                  <input
                    type="text"
                    value={formData.receiver_pincode}
                    onChange={(e) => handleChange('receiver_pincode', e.target.value)}
                    className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Receiver Email</label>
                  <input
                    type="email"
                    value={formData.receiver_email}
                    onChange={(e) => handleChange('receiver_email', e.target.value)}
                    className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
              </div>
              <div className="sm:col-span-3">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Order Description</label>
                <input
                  type="text"
                  value={formData.order_description}
                  onChange={(e) => handleChange('order_description', e.target.value)}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>
          </div>

          {/* Section 4: Boxes */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider">
                Boxes ({formData.boxes.length})
              </h4>
              <button
                type="button"
                onClick={addBox}
                className="inline-flex items-center text-xs font-medium text-indigo-600 hover:text-indigo-800"
              >
                <Plus className="w-3.5 h-3.5 mr-1" /> Add Box
              </button>
            </div>

            {formData.boxes.length === 0 ? (
              <p className="text-xs text-slate-400 italic bg-slate-50 p-3 rounded-lg border border-slate-200">
                No box information found. Will be left blank in Excel (flagged for review).
              </p>
            ) : (
              <div className="space-y-2">
                {formData.boxes.map((box, idx) => (
                  <div key={idx} className="flex items-center space-x-2 bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                    <span className="text-xs font-bold text-slate-400 w-6">#{idx + 1}</span>
                    <div className="grid grid-cols-5 gap-2 flex-1">
                      <input
                        type="number"
                        placeholder="Length"
                        value={box.length ?? ''}
                        onChange={(e) => handleBoxChange(idx, 'length', e.target.value)}
                        className="text-xs px-2 py-1 border border-slate-300 rounded"
                      />
                      <input
                        type="number"
                        placeholder="Width"
                        value={box.width ?? ''}
                        onChange={(e) => handleBoxChange(idx, 'width', e.target.value)}
                        className="text-xs px-2 py-1 border border-slate-300 rounded"
                      />
                      <input
                        type="number"
                        placeholder="Height"
                        value={box.height ?? ''}
                        onChange={(e) => handleBoxChange(idx, 'height', e.target.value)}
                        className="text-xs px-2 py-1 border border-slate-300 rounded"
                      />
                      <input
                        type="number"
                        step="0.1"
                        placeholder="Weight (kg)"
                        value={box.weight ?? ''}
                        onChange={(e) => handleBoxChange(idx, 'weight', e.target.value)}
                        className="text-xs px-2 py-1 border border-slate-300 rounded"
                      />
                      <input
                        type="number"
                        placeholder="Quantity"
                        value={box.quantity ?? ''}
                        onChange={(e) => handleBoxChange(idx, 'quantity', e.target.value)}
                        className="text-xs px-2 py-1 border border-slate-300 rounded font-semibold text-indigo-700"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => removeBox(idx)}
                      className="text-slate-400 hover:text-red-500 p-1"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end space-x-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onSave(formData)}
            className="px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition"
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

