import { useState } from 'react';
import { api } from '../api';

// Demo acknowledgement only. Production must render the full policy text and retain its versioned audit evidence.
export default function PolicyPanel({ employeeId, stage, documents = [], onSigned }) {
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const signed = stage?.status === 'complete';
  const requiredDocumentTypes = ['id_proof', 'degree_certificate', 'signed_offer_letter'];
  const verifiedTypes = new Set(
    documents
      .filter((document) => document.status === 'verified')
      .map((document) => document.doc_type || document.document_type)
  );
  const documentsVerified = requiredDocumentTypes.every((type) => verifiedTypes.has(type));

  async function sign() {
    setBusy(true);
    setError(null);
    try {
      await api.signPolicies(employeeId, { policy_id: 'company_policy', version: 'v1', accepted: true });
      await onSigned();
    } catch (err) {
      setError(err.message || 'Could not record your sign-off. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  if (signed) {
    return <p className="hint hint-ok" role="status">You accepted the company policies. Nothing more to do here.</p>;
  }

  return (
    <div>
      {!documentsVerified && (
        <p className="hint" role="status">Upload all three required documents and wait for HR verification before signing policies.</p>
      )}
      <label className="check">
        <input type="checkbox" checked={agreed} disabled={!documentsVerified || busy} onChange={(e) => setAgreed(e.target.checked)} />
        <span>I have read and accept the company policies.</span>
      </label>
      {error && <p className="hint hint-bad" role="alert">{error}</p>}
      <button className="btn btn-primary" disabled={!documentsVerified || !agreed || busy} onClick={sign}>
        {busy ? 'Saving…' : 'Sign policies'}
      </button>
    </div>
  );
}
