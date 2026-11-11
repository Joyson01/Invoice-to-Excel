import { useState } from 'react';
import { X } from 'lucide-react';
import type { ConfigData } from '../types';

export default function SettingsModal({ 
  config, 
  onClose, 
  onSave 
}: { 
  config: ConfigData; 
  onClose: () => void; 
  onSave: (cfg: ConfigData) => Promise<void>;
}) {
  const [cfg, setCfg] = useState<ConfigData>({ ...config });
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await onSave(cfg);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Unable to save defaults.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-lg w-full flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h3 className="text-base font-bold text-slate-900">Configurable Business Defaults</h3>
            <p className="text-xs text-slate-500 mt-0.5">Applies to new uploads. Defaults reset when the server restarts.</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {saveError && <p role="alert" className="text-sm text-red-700">{saveError}</p>}
          <label className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={cfg.apply_business_defaults}
              onChange={e => setCfg({ ...cfg, apply_business_defaults: e.target.checked })}
              className="mt-1"
            />
            <span>Use business defaults for missing fields
              <span className="block text-xs text-slate-500 mt-1">Off by default. When enabled, these values are added to new uploads and identified in the review warnings.</span>
            </span>
          </label>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Warehouse Name</label>
            <input
              type="text"
              value={cfg.warehouse_name}
              onChange={(e) => setCfg({ ...cfg, warehouse_name: e.target.value })}
              className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 font-mono"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Default Receiver Email</label>
            <input
              type="email"
              value={cfg.receiver_email_default}
              onChange={(e) => setCfg({ ...cfg, receiver_email_default: e.target.value })}
              className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Payment Mode</label>
              <input
                type="text"
                value={cfg.payment_mode_default}
                onChange={(e) => setCfg({ ...cfg, payment_mode_default: e.target.value })}
                className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Insurance Default</label>
              <input
                type="text"
                value={cfg.insurance_default}
                onChange={(e) => setCfg({ ...cfg, insurance_default: e.target.value })}
                className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
          <div className="grid grid-cols-4 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">Box L (cm)</label>
              <input
                type="number"
                value={cfg.box_length_default}
                onChange={(e) => setCfg({ ...cfg, box_length_default: Number(e.target.value) })}
                className="w-full text-xs px-2 py-1.5 border border-slate-300 rounded"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">Box W (cm)</label>
              <input
                type="number"
                value={cfg.box_width_default}
                onChange={(e) => setCfg({ ...cfg, box_width_default: Number(e.target.value) })}
                className="w-full text-xs px-2 py-1.5 border border-slate-300 rounded"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">Box H (cm)</label>
              <input
                type="number"
                value={cfg.box_height_default}
                onChange={(e) => setCfg({ ...cfg, box_height_default: Number(e.target.value) })}
                className="w-full text-xs px-2 py-1.5 border border-slate-300 rounded"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">Weight (kg)</label>
              <input
                type="number"
                value={cfg.box_weight_default}
                onChange={(e) => setCfg({ ...cfg, box_weight_default: Number(e.target.value) })}
                className="w-full text-xs px-2 py-1.5 border border-slate-300 rounded"
              />
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end space-x-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm"
          >
            {saving ? 'Saving…' : 'Save Defaults'}
          </button>
        </div>
      </div>
    </div>
  );
}
