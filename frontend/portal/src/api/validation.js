import { ALLOWED_CONTENT_TYPES, MAX_FILE_SIZE_BYTES, DOC_TYPES } from './constants.js';

// Client-side check only, for a better UX.
// The backend must still validate (playbook: authorization/validation is server-side).
export function validateUpload(docType, file) {
  if (!DOC_TYPES.includes(docType)) return 'Unknown document type.';
  if (!file) return 'Please choose a file.';
  if (!ALLOWED_CONTENT_TYPES.includes(file.type)) return 'Only PDF, JPG or PNG files are allowed.';
  if (file.size > MAX_FILE_SIZE_BYTES) return 'File is larger than 5 MB.';
  if (file.size === 0) return 'File is empty.';
  return null; // valid
}
