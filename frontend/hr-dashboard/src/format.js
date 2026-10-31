import { STAGES, STAGE_LABELS } from './api';

export const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '';

export const orderStages = (stages = []) =>
  STAGES.map((n) => stages.find((s) => s.stage === n)).filter(Boolean);

export function doneCount(stages) {
  return orderStages(stages).filter((s) => s.status === 'complete').length;
}

export function currentStageLabel(stages) {
  const next = orderStages(stages).find((s) => s.status !== 'complete');
  return next ? STAGE_LABELS[next.stage] : 'All stages done';
}

export const kb = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`);
