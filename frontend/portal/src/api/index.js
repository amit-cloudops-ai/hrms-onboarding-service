// Single entry point for the UI: import { api } from '../api'.
// To go live later, set VITE_USE_MOCK=false and VITE_API_BASE_URL (no secrets in git!)
// and implement httpApi.js with the same function names as mockApi.js.
import * as mockApi from './mockApi.js';

const useMock = import.meta.env?.VITE_USE_MOCK !== 'false';

export const api = mockApi; // swap to the http implementation when Amit's API is ready
export { useMock };
export { ApiError, mockSettings } from './mockApi.js';
export * from './constants.js';
export { validateUpload } from './validation.js';
export { MOCK_CURRENT_EMPLOYEE_ID } from './mockData.js';
