import React, { useState, useEffect, useRef } from 'react';
import { 
  Upload, 
  FileText, 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Download, 
  Edit3, 
  Trash2, 
  RefreshCw, 
  FileSpreadsheet, 
  AlertCircle,
  Settings
} from 'lucide-react';
import { InvoiceData, ConfigData, BatchSummary } from './types';
import { readJson } from './lib/api';
import InvoiceEditModal from './components/InvoiceEditModal';
import SettingsModal from './components/SettingsModal';

export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [invoices, setInvoices] = useState<InvoiceData[]>([]);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceData | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [downloadInfo, setDownloadInfo] = useState<{ filename: string; url: string } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [config, setConfig] = useState<ConfigData | null>(null);
  const [history, setHistory] = useState<BatchSummary[] | null>(null);
  const [isLoadingBatch, setIsLoadingBatch] = useState(false);
  const [needsReviewOnly, setNeedsReviewOnly] = useState(false);
  const needsAttention = invoices.filter(invoice => invoice.status !== 'Ready').length;
  const visibleInvoices = needsReviewOnly ? invoices.filter(invoice => invoice.status !== 'Ready') : invoices;
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch('/api/config')
      .then(res => readJson<ConfigData>(res))
      .then(data => setConfig(data))
      .catch(err => setErrorMsg(`Cannot load business defaults: ${err.message}. Check that the backend is running.`));
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
      setFiles(prev => [...prev, ...droppedFiles]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
      setFiles(prev => [...prev, ...selected]);
    }
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleExtract = async () => {
    if (files.length === 0) return;
    setIsUploading(true);
    setErrorMsg(null);
    setDownloadInfo(null);

    const formData = new FormData();
    files.forEach(f => formData.append('files', f));

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await readJson<{ detail?: string }>(res);
        throw new Error(errData.detail || 'Extraction failed');
      }

      const data = await readJson<{ session_id: string; invoices: InvoiceData[] }>(res);
      setSessionId(data.session_id);
      setInvoices(data.invoices);
    } catch (err: any) {
      setErrorMsg(err.message || 'Error uploading files');
    } finally {
      setIsUploading(false);
    }
  };

  const handleSaveInvoice = async (updated: InvoiceData) => {
    if (!sessionId) return;

    try {
      const res = await fetch(`/api/invoices/${sessionId}/${updated.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      });

      if (!res.ok) {
        throw new Error('Failed to update invoice');
      }

      const savedInv = await readJson<InvoiceData>(res);
      setDownloadInfo(null);
      setInvoices(prev => prev.map(inv => inv.id === savedInv.id ? savedInv : inv));
      const refreshed = await readJson<{ invoices: InvoiceData[] }>(await fetch(`/api/invoices/${sessionId}`));
      setInvoices(refreshed.invoices);
      setSelectedInvoice(null);
    } catch (err: any) {
      alert(`Error saving invoice: ${err.message}`);
    }
  };

  const handleGenerateExcel = async () => {
    if (!sessionId) return;
    setIsGenerating(true);
    setErrorMsg(null);

    try {
      const res = await fetch(`/api/generate/${sessionId}`, {
        method: 'POST',
      });

      if (!res.ok) {
        const errData = await readJson<{ detail?: string }>(res);
        throw new Error(errData.detail || 'Failed to generate Excel workbook');
      }

      const data = await readJson<{ filename: string; download_url: string }>(res);
      setDownloadInfo({
        filename: data.filename,
        url: data.download_url
      });
    } catch (err: any) {
      setErrorMsg(err.message || 'Error generating Excel');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveConfig = async (newCfg: ConfigData) => {
    const res = await fetch('/api/config', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newCfg),
    });
    const data = await readJson<ConfigData>(res);
    setConfig(data);
    setIsSettingsOpen(false);
  };

  const resetAll = () => {
    setHistory(null);
    setNeedsReviewOnly(false);
    setFiles([]);
    setSessionId(null);
    setInvoices([]);
    setSelectedInvoice(null);
    setDownloadInfo(null);
    setErrorMsg(null);
  };

  const openHistory = async () => {
    setErrorMsg(null);
    setIsLoadingBatch(true);
    try {
      const result = await readJson<{ batches: BatchSummary[] }>(await fetch('/api/batches'));
      setHistory(result.batches);
    } catch (error) {
      setErrorMsg((error as Error).message);
    } finally {
      setIsLoadingBatch(false);
    }
  };

  const openBatch = async (id: string) => {
    setErrorMsg(null);
    setIsLoadingBatch(true);
    try {
      const result = await readJson<{ invoices: InvoiceData[] }>(await fetch(`/api/invoices/${id}`));
      resetAll();
      setSessionId(id);
      setInvoices(result.invoices);
      setHistory(null);
    } catch (error) {
      setErrorMsg((error as Error).message);
    } finally {
      setIsLoadingBatch(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Ready':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            <CheckCircle className="w-3.5 h-3.5 mr-1" /> Ready
          </span>
        );
      case 'Review Required':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
            <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Review Required
          </span>
        );
      case 'Failed':
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
            <XCircle className="w-3.5 h-3.5 mr-1" /> Failed
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-indigo-600 p-2.5 rounded-xl shadow-md text-white">
              <FileSpreadsheet className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">B2B Invoice Extractor</h1>
              <p className="text-xs text-slate-500">PDF to Standardized B2B Bulk Upload Excel Workbook</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={openHistory} disabled={isLoadingBatch || isUploading || isGenerating}
              className="text-xs font-medium text-indigo-700 px-3 py-1.5 rounded-lg border border-indigo-200">
              Batch history
            </button>
            <button
              onClick={() => setIsSettingsOpen(true)}
              disabled={!config || isUploading || isGenerating}
              className="inline-flex items-center text-xs font-medium text-slate-600 hover:text-indigo-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-indigo-300 transition"
            >
              <Settings className="w-3.5 h-3.5 mr-1.5" /> Defaults
            </button>
            {sessionId && (
              <button
                onClick={resetAll}
                className="inline-flex items-center text-xs font-medium text-slate-600 hover:text-indigo-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-indigo-300 transition"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> New Batch
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {errorMsg && (
          <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-lg shadow-sm flex items-start">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 mr-3 flex-shrink-0" />
            <div className="text-sm text-red-700">{errorMsg}</div>
          </div>
        )}

        {/* Step 1: Upload */}
        {history !== null ? (
          <section className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold text-slate-900">Recent batches</h2>
              <button onClick={() => setHistory(null)} disabled={isLoadingBatch} className="text-sm text-indigo-700">Back</button>
            </div>
            {history.length === 0 && <p className="text-sm text-slate-600">Uploaded invoices will appear here.</p>}
            <ul className="divide-y divide-slate-200">
              {history.map(batch => (
                <li key={batch.session_id}>
                  <button onClick={() => openBatch(batch.session_id)} disabled={isLoadingBatch}
                    className="flex flex-wrap gap-2 justify-between w-full py-3 text-left text-sm">
                    <span className="font-medium text-indigo-700 break-all">{batch.filename}</span>
                    <span className="text-slate-600">{batch.count} invoices · {batch.needs_attention} need attention</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : invoices.length === 0 ? (
          <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-3xl mx-auto">
            <div 
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-slate-300 hover:border-indigo-500 rounded-xl p-10 text-center cursor-pointer transition bg-slate-50 hover:bg-indigo-50/30 group"
            >
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileSelect} 
                multiple 
                accept=".pdf" 
                className="hidden" 
              />
              <div className="w-14 h-14 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition">
                <Upload className="w-7 h-7" />
              </div>
              <h3 className="text-base font-semibold text-slate-800">
                Drag & drop invoice PDFs here
              </h3>
              <p className="text-sm text-slate-500 mt-1">
                Upload PDF invoices, including scanned copies. Missing or uncertain fields stay blank for review.
              </p>
              <p className="text-xs text-slate-500 mt-2">
                {config?.apply_business_defaults ? 'Business defaults are enabled for missing fields.' : 'Business defaults are off. Only values found on the invoice are filled.'}
              </p>
              <button 
                type="button"
                className="mt-4 px-4 py-2 bg-white text-indigo-600 border border-indigo-200 rounded-lg text-sm font-medium shadow-sm hover:bg-indigo-50"
              >
                Browse Files
              </button>
            </div>

            {files.length > 0 && (
              <div className="mt-6 space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Selected Files ({files.length})
                </h4>
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1">
                  {files.map((file, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm">
                      <div className="flex items-center space-x-2 truncate">
                        <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                        <span className="font-medium text-slate-700 truncate">{file.name}</span>
                        <span className="text-xs text-slate-400">({(file.size / 1024).toFixed(1)} KB)</span>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                        className="text-slate-400 hover:text-red-500 p-1"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="pt-4 flex justify-end">
                  <button
                    onClick={handleExtract}
                    disabled={isUploading}
                    className="inline-flex items-center px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white rounded-xl text-sm font-semibold shadow-md shadow-indigo-100 transition"
                  >
                    {isUploading ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Extracting Invoices...
                      </>
                    ) : (
                      <>Extract Invoices ({files.length})</>
                    )}
                  </button>
                </div>
              </div>
            )}
          </section>
        ) : (
          /* Step 2: Review Table */
          <div className="space-y-6">
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Extracted Invoices ({invoices.length})</h2>
                <p className="text-sm text-slate-600">{invoices.length - needsAttention} ready · {needsAttention} need attention</p>
                <label className="mt-2 flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" checked={needsReviewOnly} onChange={event => setNeedsReviewOnly(event.target.checked)} />
                  Show only invoices that need attention
                </label>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={handleGenerateExcel}
                  disabled={isGenerating}
                  className="inline-flex items-center px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white rounded-xl text-sm font-semibold shadow-md shadow-emerald-100 transition"
                >
                  {isGenerating ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Generating Workbook...
                    </>
                  ) : (
                    <>
                      <FileSpreadsheet className="w-4 h-4 mr-2" />
                      GENERATE EXCEL
                    </>
                  )}
                </button>
              </div>
            </div>

            {downloadInfo && (
              <div className="bg-emerald-50 border border-emerald-200 p-5 rounded-xl shadow-sm flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center flex-shrink-0">
                    <CheckCircle className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-emerald-900">Workbook Ready!</h4>
                    <p className="text-xs text-emerald-700">{downloadInfo.filename}</p>
                  </div>
                </div>
                <a
                  href={downloadInfo.url}
                  download={downloadInfo.filename}
                  className="inline-flex items-center px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold rounded-lg shadow transition"
                >
                  <Download className="w-4 h-4 mr-1.5" />
                  Download Excel
                </a>
              </div>
            )}

            {/* Table */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                  <thead className="bg-slate-50 font-semibold text-slate-700 uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3">File</th>
                      <th className="px-4 py-3">Order_ID</th>
                      <th className="px-4 py-3">Receiver</th>
                      <th className="px-4 py-3">Pincode</th>
                      <th className="px-4 py-3">Mobile</th>
                      <th className="px-4 py-3">Invoice Number</th>
                      <th className="px-4 py-3">Invoice Amount</th>
                      <th className="px-4 py-3">E-Way Bill</th>
                      <th className="px-4 py-3">Boxes</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {visibleInvoices.map((inv) => (
                      <tr 
                        key={inv.id} 
                        onClick={() => setSelectedInvoice(inv)}
                        className="hover:bg-indigo-50/40 cursor-pointer transition"
                      >
                        <td className="px-4 py-3 font-medium text-slate-900 flex items-center space-x-1.5">
                          <FileText className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                          <span className="truncate max-w-[130px]">{inv.filename}</span>
                        </td>
                        <td className="px-4 py-3 font-semibold text-indigo-600">{inv.order_id || <span className="text-slate-300">-</span>}</td>
                        <td className="px-4 py-3 text-slate-700 truncate max-w-[140px]">{inv.receiver_name || <span className="text-slate-300">-</span>}</td>
                        <td className="px-4 py-3 text-slate-700">{inv.receiver_pincode || <span className="text-slate-300">-</span>}</td>
                        <td className="px-4 py-3 text-slate-700">{inv.receiver_mobile || <span className="text-slate-300">-</span>}</td>
                        <td className="px-4 py-3 text-slate-700">{inv.invoice_number || <span className="text-slate-300">-</span>}</td>
                        <td className="px-4 py-3 font-medium text-slate-800">
                          {inv.invoice_amount !== null && inv.invoice_amount !== undefined 
                            ? `₹${inv.invoice_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` 
                            : <span className="text-slate-300">-</span>}
                        </td>
                        <td className="px-4 py-3 text-slate-700">{inv.eway_bill_number || <span className="text-slate-300">-</span>}</td>
                        <td className="px-4 py-3 text-slate-700">
                          {inv.boxes.length > 0 && inv.boxes.every(b => b.quantity != null)
                            ? `${inv.boxes.reduce((acc, b) => acc + (b.quantity ?? 0), 0)} boxes`
                            : <span className="text-slate-400">Not found</span>}
                        </td>
                        <td className="px-4 py-3">{getStatusBadge(inv.status)}
                          {inv.warnings.length > 0 && <p className="mt-1 max-w-48 text-slate-600">{inv.warnings[0]}</p>}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={(e) => { e.stopPropagation(); setSelectedInvoice(inv); }}
                            className="inline-flex items-center text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1 rounded-md transition"
                          >
                            <Edit3 className="w-3.5 h-3.5 mr-1" /> Edit
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {visibleInvoices.length === 0 && <p className="p-5 text-sm text-slate-600">No invoices need attention.</p>}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Edit Form Modal */}
      {selectedInvoice && (
        <InvoiceEditModal
          invoice={selectedInvoice}
          config={config}
          onClose={() => setSelectedInvoice(null)}
          onSave={handleSaveInvoice}
        />
      )}

      {/* Settings Modal */}
      {isSettingsOpen && config && (
        <SettingsModal
          config={config}
          onClose={() => setIsSettingsOpen(false)}
          onSave={handleSaveConfig}
        />
      )}
    </div>
  );
}

