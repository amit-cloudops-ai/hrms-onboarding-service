import { useCallback } from 'react';
import { api, mockSettings, MOCK_CURRENT_EMPLOYEE_ID } from './api';
import { useAsync } from './hooks/useAsync';
import { Loading, ErrorState } from './components/StateViews';
import StageTimeline from './components/StageTimeline';
import DocumentsPanel from './components/DocumentsPanel';
import PolicyPanel from './components/PolicyPanel';
import './App.css';

// TODO(real login): employee_id will come from the Cognito session. Mock for now.
const EMPLOYEE_ID = MOCK_CURRENT_EMPLOYEE_ID;

export default function App() {
  const load = useCallback(async () => {
    const [employee, stages, documents] = await Promise.all([
      api.getEmployee(EMPLOYEE_ID),
      api.getProgress(EMPLOYEE_ID),
      api.listDocuments(EMPLOYEE_ID),
    ]);
    return { employee, stages, documents };
  }, []);

  const { data, error, loading, reload } = useAsync(load);

  // Re-fetch without blanking the screen after an upload / sign-off.
  const refresh = async () => { await reload(); };

  return (
    <div className="page">
      {loading && !data && <Loading label="Loading your onboarding…" />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && (
        <>
          <header className="hero">
            <h1>Welcome, {data.employee.full_name.split(' ')[0]}</h1>
            <p>
              {data.employee.role}, {data.employee.department}. You join on{' '}
              {new Date(data.employee.joining_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}.
            </p>
          </header>

          <main className="grid">
            <section className="panel" aria-labelledby="h-progress">
              <h2 id="h-progress">Your progress</h2>
              <StageTimeline stages={data.stages} />
            </section>

            <div className="stack">
              <section className="panel" aria-labelledby="h-docs">
                <h2 id="h-docs">Documents</h2>
                <DocumentsPanel employeeId={EMPLOYEE_ID} documents={data.documents} onChanged={refresh} />
              </section>

              <section className="panel" aria-labelledby="h-policy">
                <h2 id="h-policy">Policy sign-off</h2>
                <PolicyPanel
                  employeeId={EMPLOYEE_ID}
                  stage={data.stages.find((s) => s.stage === 'policy_signoff')}
                  onSigned={refresh}
                />
              </section>
            </div>
          </main>
        </>
      )}

      {/* Demo helper for screenshots. Remove before connecting the real API. */}
      <footer className="demo">
        <span>Demo controls (mock data):</span>
        <button onClick={() => { mockSettings.failNext = true; reload(); }}>Simulate error</button>
        <button onClick={() => { mockSettings.delayMs = mockSettings.delayMs > 600 ? 600 : 3000; }}>Toggle slow network</button>
      </footer>
    </div>
  );
}
