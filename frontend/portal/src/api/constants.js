// Shared names from docs/api-contract.md and docs/team-playbook.md.
// Do NOT rename these here only - change the contract first (talk to Amit).

export const STAGES = [
  'document_collection',
  'it_provisioning',
  'policy_signoff',
  'manager_intro',
];

export const STAGE_STATUS = ['pending', 'in_progress', 'complete'];

export const DOC_TYPES = ['id_proof', 'degree_certificate', 'signed_offer_letter'];

export const DOC_STATUS = ['missing', 'uploaded', 'verified', 'rejected'];

export const ALLOWED_CONTENT_TYPES = ['application/pdf', 'image/jpeg', 'image/png'];
export const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

// Display labels (UI only, not part of the contract)
export const STAGE_LABELS = {
  document_collection: 'Document collection',
  it_provisioning: 'IT provisioning',
  policy_signoff: 'Policy sign-off',
  manager_intro: 'Manager introduction',
};

export const DOC_LABELS = {
  id_proof: 'ID proof',
  degree_certificate: 'Degree certificate',
  signed_offer_letter: 'Signed offer letter',
};
