import { STAGES } from '../api';
import { orderStages } from '../format';

// Four small bars, one per stage, coloured by status.
export default function StageSegments({ stages }) {
  const ordered = orderStages(stages);
  const done = ordered.filter((s) => s.status === 'complete').length;
  return (
    <span className="segs" role="img" aria-label={`${done} of ${STAGES.length} stages complete`}>
      {STAGES.map((name) => {
        const s = ordered.find((x) => x.stage === name);
        return <span key={name} className={`seg seg-${s ? s.status : 'pending'}`} />;
      })}
    </span>
  );
}
