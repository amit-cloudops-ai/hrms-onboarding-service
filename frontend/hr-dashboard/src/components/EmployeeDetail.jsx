import { useCallback, useState } from 'react';
import { api, STAGE_LABELS, DOC_LABELS } from '../api';
import { useAsync } from '../hooks/useAsync';
import { Loading, ErrorState } from './StateViews';
import { fmtDate, kb, orderStages } from '../format';

const STAGE_TEXT = { pending: 'Not started', in_progress: 'In progress', complete: 'Done' };
const DOC_TEXT = { missing: 'Missing', uploaded: 'Uploaded', verified: 'Verified', rejected: 'Rejected' };

// NOTE: the contract has no route for HR to verify/reject documents, so documents are read-only here.
export default function EmployeeDetail({ employee, onChanged, onClose }) {
  const id = employee.employee_id;
  const load = useCallback(async () => {
    const [stages, documents] = await Promise.all([api.getProgress(id), api.listDocuments(id)]);
    return { stages, documents };
  }, [id]);
  const { data, error, loading, reload } = useAsync(load);

  const [confirming, setConfirming] = useState(null); // stage waiting for a second click
  const [busy, setBusy] = useState(null);
  const [actionError, setActionError] = useState(null);

  async function complete(stage) {
    setBusy(stage);
    setActionError(null);
    try {
      await api.completeStage(id, stage);
      setConfirming(null);
      await reload();
      await onChanged();
    } catch (err) {
      setActionError(err.message || 'Could not update the stage. Please try again.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <aside className="detail" aria-label={`Details for ${employee.full_name}`}>
      <div className="detail-head">
        <div>
          <h2>{employee.full_name}</h2>
          <p className="sub">{employee.role}, {employee.department}</p>
          <p className="sub">{employee.email} · joins {fmtDate(employee.joining_date)}</p>
        </div>
        <button className="btn btn-quiet" onClick={onClose} aria-label="Close details">Close</button>
      </div>

      {loading && !data && <Loading label="Loading details…" />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && (
        <>
          <h3>Stages</h3>
          {actionError && <p className="hint hint-bad" role="alert">{actionError}</p>}
          <ul className="plain">
            {orderStages(data.stages).map((s) => (
              <li key={s.stage} className="stage-row">
                <div>
                  <div className="strong">{STAGE_LABELS[s.stage]}</div>
                  <span className={`badge badge-${s.status}`}>{STAGE_TEXT[s.status]}</span>
                  {s.completed_at && <span className="sub"> {fmtDate(s.completed_at)}</span>}
                </div>
                {s.status !== 'complete' && (
                  confirming === s.stage ? (
                    <span className="actions">
                      <button className="btn btn-primary" disabled={busy === s.stage} onClick={() => complete(s.stage)}>
                        {busy === s.stage ? 'Saving…' : 'Confirm'}
                      </button>
                      <button className="btn btn-quiet" disabled={busy === s.stage} onClick={() => setConfirming(null)}>Cancel</button>
                    </span>
                  ) : (
                    <button className="btn" onClick={() => setConfirming(s.stage)}>Mark complete</button>
                  )
                )}
              </li>
            ))}
          </ul>

          <h3>Documents</h3>
          <ul className="plain">
            {data.documents.map((d) => (
              <li key={d.doc_type} className="stage-row">
                <div>
                  <div className="strong">{DOC_LABELS[d.doc_type]}</div>
                  {d.file_size && <span className="sub">{kb(d.file_size)}</span>}
                </div>
                <span className={`badge badge-${d.status}`}>{DOC_TEXT[d.status]}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
