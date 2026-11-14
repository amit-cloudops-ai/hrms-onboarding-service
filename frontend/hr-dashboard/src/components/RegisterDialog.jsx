import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

// ASSUMPTION (ask Amit): allowed employment_type values.
const TYPES = [
  { value: 'full_time', label: 'Full time' },
  { value: 'part_time', label: 'Part time' },
  { value: 'contract', label: 'Contract' },
];

const EMPTY = { full_name: '', email: '', department: '', role: '', joining_date: '', employment_type: 'full_time' };
const FIELDS = [
  ['full_name', 'Full name', 'text'],
  ['email', 'Work email', 'email'],
  ['department', 'Department', 'text'],
  ['role', 'Job title', 'text'],
  ['joining_date', 'Joining date', 'date'],
];

function Form({ onCancel, onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  function validate() {
    const errs = {};
    for (const [k, label] of FIELDS) if (!form[k].trim()) errs[k] = `${label} is required.`;
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = 'Enter a valid email address.';
    return errs;
  }

  async function submit(e) {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setSubmitError(null);
    try {
      const created = await api.createEmployee({ ...form, full_name: form.full_name.trim(), email: form.email.trim() });
      await onCreated(created);
    } catch (err) {
      setSubmitError(err.message || 'Could not register the new hire. Please try again.');
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <h2>Register new hire</h2>
      {FIELDS.map(([k, label, type]) => (
        <div className="field" key={k}>
          <label htmlFor={`f-${k}`}>{label}</label>
          <input id={`f-${k}`} type={type} value={form[k]} onChange={set(k)}
            aria-invalid={!!errors[k]} aria-describedby={errors[k] ? `e-${k}` : undefined} />
          {errors[k] && <span id={`e-${k}`} className="hint hint-bad">{errors[k]}</span>}
        </div>
      ))}
      <div className="field">
        <label htmlFor="f-type">Employment type</label>
        <select id="f-type" value={form.employment_type} onChange={set('employment_type')}>
          {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>
      {submitError && <p className="hint hint-bad" role="alert">{submitError}</p>}
      <div className="dialog-actions">
        <button type="button" className="btn btn-quiet" onClick={onCancel} disabled={busy}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Registering…' : 'Register hire'}</button>
      </div>
    </form>
  );
}

export default function RegisterDialog({ open, onClose, onCreated }) {
  const ref = useRef(null);
  useEffect(() => {
    const d = ref.current;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog ref={ref} className="dialog" onClose={onClose}>
      {open && <Form onCancel={onClose} onCreated={onCreated} />}
    </dialog>
  );
}
