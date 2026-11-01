import { STAGES, STAGE_LABELS } from '../api';
import { Empty } from './StateViews';

const STATUS_TEXT = { pending: 'Not started', in_progress: 'In progress', complete: 'Done' };

const fmt = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : null;

export default function StageTimeline({ stages }) {
  if (!stages || stages.length === 0) {
    return <Empty title="No stages yet">Your onboarding steps will appear here once HR starts the process.</Empty>;
  }
  const ordered = STAGES.map((name) => stages.find((s) => s.stage === name)).filter(Boolean);
  const done = ordered.filter((s) => s.status === 'complete').length;
  const pct = Math.round((done / STAGES.length) * 100);

  return (
    <div>
      <div className="progress-head">
        <span>{done} of {STAGES.length} steps done</span>
        <span>{pct}%</span>
      </div>
      <div className="bar" role="progressbar" aria-valuenow={pct} aria-valuemin="0" aria-valuemax="100">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>

      <ol className="timeline">
        {ordered.map((s, i) => (
          <li key={s.stage} className={`tl-item tl-${s.status}`}>
            <span className="tl-marker" aria-hidden="true">{s.status === 'complete' ? '✓' : i + 1}</span>
            <div>
              <div className="tl-title">{STAGE_LABELS[s.stage]}</div>
              <div className="tl-meta">
                <span className={`badge badge-${s.status}`}>{STATUS_TEXT[s.status]}</span>
                {s.completed_at && <span> Completed {fmt(s.completed_at)}</span>}
                {!s.completed_at && s.started_at && <span> Started {fmt(s.started_at)}</span>}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
