import { useMemo, useState } from 'react';
import { api, mockSettings } from './api';
import { useAsync } from './hooks/useAsync';
import { Loading, ErrorState, Empty } from './components/StateViews';
import EmployeeTable from './components/EmployeeTable';
import EmployeeDetail from './components/EmployeeDetail';
import RegisterDialog from './components/RegisterDialog';
import './App.css';

export default function App() {
  const { data: employees, error, loading, reload } = useAsync(api.listEmployees);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [selectedId, setSelectedId] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [toast, setToast] = useState(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (employees ?? []).filter(
      (e) =>
        (status === 'all' || e.status === status) &&
        (!q || e.full_name.toLowerCase().includes(q) || e.email.toLowerCase().includes(q)),
    );
  }, [employees, query, status]);

  const selected = (employees ?? []).find((e) => e.employee_id === selectedId) ?? null;
  const onboarding = (employees ?? []).filter((e) => e.status === 'onboarding').length;

  function showToast(msg) {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  }

  async function handleCreated(emp) {
    setDialogOpen(false);
    await reload();
    setSelectedId(emp.employee_id);
    showToast(`${emp.full_name} was registered. Onboarding has started.`);
  }

  const clearFilters = () => { setQuery(''); setStatus('all'); };

  return (
    <>
      <header className="topbar">
        <h1>Onboarding · HR</h1>
        <button className="btn btn-primary" onClick={() => setDialogOpen(true)}>Register new hire</button>
      </header>

      <div className="page">
        {toast && <p className="toast" role="status">{toast}</p>}

        {loading && !employees && <Loading label="Loading employees…" />}
        {error && <ErrorState message={error} onRetry={reload} />}

        {employees && (
          <>
            <p className="summary">
              {employees.length} {employees.length === 1 ? 'employee' : 'employees'}, {onboarding} still onboarding
            </p>

            <div className="toolbar">
              <div className="field field-inline">
                <label htmlFor="search">Search</label>
                <input id="search" type="search" placeholder="Name or email" value={query} onChange={(e) => setQuery(e.target.value)} />
              </div>
              <div className="field field-inline">
                <label htmlFor="status">Status</label>
                <select id="status" value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="all">All</option>
                  <option value="onboarding">Onboarding</option>
                  <option value="ready">Ready</option>
                </select>
              </div>
            </div>

            <div className={`layout ${selected ? 'with-detail' : ''}`}>
              <section className="panel" aria-label="Employees">
                {employees.length === 0 ? (
                  <Empty title="No employees yet">Register the first new hire to start onboarding.</Empty>
                ) : filtered.length === 0 ? (
                  <div className="state">
                    <strong>No matches</strong>
                    <p>No employee fits this search and status.</p>
                    <button className="btn" onClick={clearFilters}>Clear filters</button>
                  </div>
                ) : (
                  <EmployeeTable employees={filtered} selectedId={selectedId} onSelect={setSelectedId} />
                )}
              </section>

              {selected && (
                <EmployeeDetail key={selected.employee_id} employee={selected} onChanged={reload} onClose={() => setSelectedId(null)} />
              )}
            </div>
          </>
        )}

        {/* Demo helper for screenshots. Remove before connecting the real API. */}
        <footer className="demo">
          <span>Demo controls (mock data):</span>
          <button onClick={() => { mockSettings.failNext = true; reload(); }}>Simulate error</button>
          <button onClick={() => { mockSettings.delayMs = mockSettings.delayMs > 600 ? 600 : 3000; }}>Toggle slow network</button>
        </footer>
      </div>

      <RegisterDialog open={dialogOpen} onClose={() => setDialogOpen(false)} onCreated={handleCreated} />
    </>
  );
}
