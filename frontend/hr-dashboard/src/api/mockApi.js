// Mock implementation of the 8 routes in docs/api-contract.md.
// Every function mirrors one route. Replace this file's logic with
// real fetch() calls later; components never import mockData directly.
//
// ASSUMPTIONS (confirm with Amit; response shapes are not in the contract yet):
//  - list/detail/progress/documents return plain objects/arrays as below
//  - upload-url returns { upload_url, doc_type, expires_in_seconds }
//  - policies/sign accepts no body and marks policy_signoff complete

import { STAGES, DOC_TYPES } from './constants.js';
import { validateUpload } from './validation.js';
import { seedEmployees, seedStages, seedDocuments } from './mockData.js';

const clone = (x) => JSON.parse(JSON.stringify(x));

// In-memory "database" (resets on page refresh)
let employees = clone(seedEmployees);
let stages = clone(seedStages);
let documents = clone(seedDocuments);

// Dev controls so we can demo loading / error states.
export const mockSettings = { delayMs: 600, failNext: false };

export class ApiError extends Error {
  constructor(message, status = 500) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function simulate() {
  await new Promise((r) => setTimeout(r, mockSettings.delayMs));
  if (mockSettings.failNext) {
    mockSettings.failNext = false;
    throw new ApiError('Something went wrong. Please try again.', 500);
  }
}

function findEmployee(id) {
  const e = employees.find((x) => x.employee_id === id);
  if (!e) throw new ApiError('Employee not found.', 404);
  return e;
}

function nowIso() {
  return new Date().toISOString();
}

// POST /employees  (HR admin)
export async function createEmployee(payload) {
  await simulate();
  const required = ['full_name', 'email', 'department', 'role', 'joining_date', 'employment_type'];
  for (const f of required) {
    if (!payload?.[f]) throw new ApiError(`Missing field: ${f}`, 400);
  }
  const employee_id = crypto.randomUUID();
  const emp = {
    employee_id,
    full_name: payload.full_name,
    email: payload.email,
    department: payload.department,
    role: payload.role,
    manager_id: payload.manager_id ?? null,
    joining_date: payload.joining_date,
    employment_type: payload.employment_type,
    status: 'onboarding',
    created_at: nowIso(),
  };
  employees.push(emp);
  stages[employee_id] = STAGES.map((stage, i) => ({
    stage,
    status: i === 0 ? 'in_progress' : 'pending',
    started_at: i === 0 ? nowIso() : null,
    completed_at: null,
  }));
  documents[employee_id] = DOC_TYPES.map((doc_type) => ({
    doc_type, status: 'missing', file_size: null, content_type: null, validated_at: null,
  }));
  return clone(emp);
}

// GET /employees  (HR admin) - list with stage status for the dashboard
export async function listEmployees() {
  await simulate();
  return clone(employees.map((e) => ({ ...e, stages: stages[e.employee_id] ?? [] })));
}

// GET /employees/{employee_id}
export async function getEmployee(employeeId) {
  await simulate();
  return clone(findEmployee(employeeId));
}

// GET /employees/{employee_id}/progress
export async function getProgress(employeeId) {
  await simulate();
  findEmployee(employeeId);
  return clone(stages[employeeId] ?? []);
}

// POST /employees/{employee_id}/documents/upload-url  (that employee)
export async function requestUploadUrl(employeeId, { doc_type, content_type, file_size }) {
  await simulate();
  findEmployee(employeeId);
  const problem = validateUpload(doc_type, { type: content_type, size: file_size });
  if (problem) throw new ApiError(problem, 400);
  return { upload_url: `https://mock-upload.invalid/${employeeId}/${doc_type}`, doc_type, expires_in_seconds: 300 };
}

// Mock-only stand-in for "PUT file to the one-time URL" (real one goes straight to S3).
export async function uploadToUrl(employeeId, docType, file) {
  await simulate();
  const row = (documents[employeeId] ?? []).find((d) => d.doc_type === docType);
  if (!row) throw new ApiError('Document type not found.', 404);
  row.status = 'uploaded';
  row.file_size = file.size;
  row.content_type = file.type;
  row.validated_at = nowIso();
  return { ok: true };
}

// GET /employees/{employee_id}/documents
export async function listDocuments(employeeId) {
  await simulate();
  findEmployee(employeeId);
  return clone(documents[employeeId] ?? []);
}

// POST /employees/{employee_id}/policies/sign  (that employee)
export async function signPolicies(employeeId) {
  await simulate();
  findEmployee(employeeId);
  const row = (stages[employeeId] ?? []).find((s) => s.stage === 'policy_signoff');
  if (!row) throw new ApiError('Stage not found.', 404);
  row.status = 'complete';
  row.started_at = row.started_at ?? nowIso();
  row.completed_at = nowIso();
  return { stage: 'policy_signoff', status: 'complete' };
}

// POST /employees/{employee_id}/stages/{stage}/complete  (HR admin)
export async function completeStage(employeeId, stage) {
  await simulate();
  findEmployee(employeeId);
  if (!STAGES.includes(stage)) throw new ApiError('Unknown stage.', 400);
  const row = (stages[employeeId] ?? []).find((s) => s.stage === stage);
  if (!row) throw new ApiError('Stage not found.', 404);
  row.status = 'complete';
  row.started_at = row.started_at ?? nowIso();
  row.completed_at = nowIso();
  const allDone = stages[employeeId].every((s) => s.status === 'complete');
  if (allDone) findEmployee(employeeId).status = 'ready';
  return clone(row);
}
