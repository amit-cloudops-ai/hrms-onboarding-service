import { useState } from 'react';
import { api, DOC_LABELS, validateUpload } from '../api';
import { Empty } from './StateViews';

const STATUS_TEXT = { missing: 'Needed', uploaded: 'Uploaded, awaiting review', verified: 'Verified', rejected: 'Rejected' };

const kb = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`);

function DocRow({ employeeId, doc, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [justUploaded, setJustUploaded] = useState(false);
  const inputId = `file-${doc.doc_type}`;

  async function handleFile(e) {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow choosing the same file again
    setError(null);
    setJustUploaded(false);

    const problem = validateUpload(doc.doc_type, file);
    if (problem) { setError(problem); return; }

    setBusy(true);
    try {
      await api.requestUploadUrl(employeeId, {
        doc_type: doc.doc_type, content_type: file.type, file_size: file.size,
      });
      await api.uploadToUrl(employeeId, doc.doc_type, file);
      setJustUploaded(true);
      await onChanged();
    } catch (err) {
      setError(err.message || 'Upload failed. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  const canUpload = doc.status !== 'verified';
  const label = doc.status === 'missing' ? 'Choose file' : 'Replace file';

  return (
    <li className="doc">
      <div className="doc-main">
        <div className="doc-title">{DOC_LABELS[doc.doc_type]}</div>
        <div className="tl-meta">
          <span className={`badge badge-${doc.status}`}>{STATUS_TEXT[doc.status]}</span>
          {doc.file_size && <span> {kb(doc.file_size)}</span>}
        </div>
        {doc.status === 'rejected' && <p className="hint hint-bad">This file was rejected. Upload a clearer copy.</p>}
        {justUploaded && <p className="hint hint-ok" role="status">Uploaded. HR will review it shortly.</p>}
        {error && <p className="hint hint-bad" role="alert">{error}</p>}
      </div>
      {canUpload && (
        <>
          <input id={inputId} type="file" className="visually-hidden"
            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            onChange={handleFile} disabled={busy} />
          <label htmlFor={inputId} className={`btn ${busy ? 'btn-disabled' : ''}`}>
            {busy ? 'Uploading…' : label}
          </label>
        </>
      )}
    </li>
  );
}

export default function DocumentsPanel({ employeeId, documents, onChanged }) {
  if (!documents || documents.length === 0) {
    return <Empty title="No documents requested">HR has not asked for any documents yet.</Empty>;
  }
  return (
    <>
      <p className="muted">PDF, JPG or PNG. Maximum 5 MB per file.</p>
      <ul className="doc-list">
        {documents.map((d) => (
          <DocRow key={d.doc_type} employeeId={employeeId} doc={d} onChanged={onChanged} />
        ))}
      </ul>
    </>
  );
}
