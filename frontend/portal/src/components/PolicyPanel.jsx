import { useState } from 'react';
import { api } from '../api';

// NOTE: the contract only has POST /employees/{id}/policies/sign (no policy text/list).
// We show a single acceptance. Ask Amit if individual policies must be listed.
export default function PolicyPanel({ employeeId, stage, onSigned }) {
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const signed = stage?.status === 'complete';

  async function sign() {
    setBusy(true);
    setError(null);
    try {
      await api.signPolicies(employeeId);
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
      <label className="check">
        <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
        <span>I have read and accept the company policies.</span>
      </label>
      {error && <p className="hint hint-bad" role="alert">{error}</p>}
      <button className="btn btn-primary" disabled={!agreed || busy} onClick={sign}>
        {busy ? 'Saving…' : 'Sign policies'}
      </button>
    </div>
  );
}
