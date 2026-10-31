// Fake data shaped like docs/data-model.md.
// Intentionally kept apart from the API functions so it is easy to delete later.
//
// NOT sent to the frontend (backend-only): execution_arn, task_token, s3_key.
//
// ASSUMPTION (ask Amit): allowed values of employee `status`.
// Used here: 'onboarding' | 'ready'.

const iso = (d) => new Date(d).toISOString();

export const seedEmployees = [
  {
    employee_id: '11111111-1111-4111-8111-111111111111',
    full_name: 'Priya Raman',
    email: 'priya.raman@example.com',
    department: 'Engineering',
    role: 'Backend Developer',
    manager_id: 'a0000000-0000-4000-8000-000000000001',
    joining_date: '2026-11-10',
    employment_type: 'full_time',
    status: 'onboarding',
    created_at: iso('2026-10-20'),
  },
  {
    employee_id: '22222222-2222-4222-8222-222222222222',
    full_name: 'Arjun Mehta',
    email: 'arjun.mehta@example.com',
    department: 'Finance',
    role: 'Financial Analyst',
    manager_id: 'a0000000-0000-4000-8000-000000000002',
    joining_date: '2026-11-03',
    employment_type: 'full_time',
    status: 'onboarding',
    created_at: iso('2026-10-15'),
  },
  {
    employee_id: '33333333-3333-4333-8333-333333333333',
    full_name: 'Sara Thomas',
    email: 'sara.thomas@example.com',
    department: 'Design',
    role: 'UX Designer',
    manager_id: 'a0000000-0000-4000-8000-000000000003',
    joining_date: '2026-10-28',
    employment_type: 'contract',
    status: 'ready',
    created_at: iso('2026-10-01'),
  },
];

// key: employee_id -> list of stage rows (PK employee_id, SK stage)
export const seedStages = {
  '11111111-1111-4111-8111-111111111111': [
    { stage: 'document_collection', status: 'in_progress', started_at: iso('2026-10-20'), completed_at: null },
    { stage: 'it_provisioning', status: 'pending', started_at: null, completed_at: null },
    { stage: 'policy_signoff', status: 'pending', started_at: null, completed_at: null },
    { stage: 'manager_intro', status: 'pending', started_at: null, completed_at: null },
  ],
  '22222222-2222-4222-8222-222222222222': [
    { stage: 'document_collection', status: 'complete', started_at: iso('2026-10-15'), completed_at: iso('2026-10-18') },
    { stage: 'it_provisioning', status: 'complete', started_at: iso('2026-10-18'), completed_at: iso('2026-10-22') },
    { stage: 'policy_signoff', status: 'in_progress', started_at: iso('2026-10-22'), completed_at: null },
    { stage: 'manager_intro', status: 'pending', started_at: null, completed_at: null },
  ],
  '33333333-3333-4333-8333-333333333333': [
    { stage: 'document_collection', status: 'complete', started_at: iso('2026-10-01'), completed_at: iso('2026-10-03') },
    { stage: 'it_provisioning', status: 'complete', started_at: iso('2026-10-03'), completed_at: iso('2026-10-07') },
    { stage: 'policy_signoff', status: 'complete', started_at: iso('2026-10-07'), completed_at: iso('2026-10-09') },
    { stage: 'manager_intro', status: 'complete', started_at: iso('2026-10-09'), completed_at: iso('2026-10-12') },
  ],
};

// key: employee_id -> list of document rows (PK employee_id, SK doc_type)
export const seedDocuments = {
  '11111111-1111-4111-8111-111111111111': [
    { doc_type: 'id_proof', status: 'uploaded', file_size: 482113, content_type: 'application/pdf', validated_at: iso('2026-10-21') },
    { doc_type: 'degree_certificate', status: 'missing', file_size: null, content_type: null, validated_at: null },
    { doc_type: 'signed_offer_letter', status: 'rejected', file_size: 90210, content_type: 'image/png', validated_at: iso('2026-10-22') },
  ],
  '22222222-2222-4222-8222-222222222222': [
    { doc_type: 'id_proof', status: 'verified', file_size: 310000, content_type: 'image/jpeg', validated_at: iso('2026-10-16') },
    { doc_type: 'degree_certificate', status: 'verified', file_size: 1200000, content_type: 'application/pdf', validated_at: iso('2026-10-17') },
    { doc_type: 'signed_offer_letter', status: 'verified', file_size: 250000, content_type: 'application/pdf', validated_at: iso('2026-10-18') },
  ],
  '33333333-3333-4333-8333-333333333333': [
    { doc_type: 'id_proof', status: 'verified', file_size: 300000, content_type: 'image/png', validated_at: iso('2026-10-02') },
    { doc_type: 'degree_certificate', status: 'verified', file_size: 900000, content_type: 'application/pdf', validated_at: iso('2026-10-02') },
    { doc_type: 'signed_offer_letter', status: 'verified', file_size: 240000, content_type: 'application/pdf', validated_at: iso('2026-10-03') },
  ],
};

// The employee the portal pretends to be logged in as (mock only).
export const MOCK_CURRENT_EMPLOYEE_ID = '11111111-1111-4111-8111-111111111111';
