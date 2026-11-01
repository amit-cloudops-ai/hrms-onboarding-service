import StageSegments from './StageSegments';
import { currentStageLabel, doneCount, fmtDate } from '../format';

const STATUS_TEXT = { onboarding: 'Onboarding', ready: 'Ready' };

export default function EmployeeTable({ employees, selectedId, onSelect }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Employee</th>
            <th scope="col">Role</th>
            <th scope="col">Joining</th>
            <th scope="col">Stage progress</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {employees.map((e) => (
            <tr key={e.employee_id} className={e.employee_id === selectedId ? 'row-selected' : ''}>
              <td>
                <button className="link" onClick={() => onSelect(e.employee_id)} aria-pressed={e.employee_id === selectedId}>
                  {e.full_name}
                </button>
                <div className="sub">{e.email}</div>
              </td>
              <td>{e.role}<div className="sub">{e.department}</div></td>
              <td>{fmtDate(e.joining_date)}</td>
              <td>
                <StageSegments stages={e.stages} />
                <div className="sub">{doneCount(e.stages)}/4 · {currentStageLabel(e.stages)}</div>
              </td>
              <td><span className={`badge badge-${e.status}`}>{STATUS_TEXT[e.status] ?? e.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
