import { getAccessToken } from "../auth.js";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status = 500, code = "API_ERROR") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request(path, options = {}) {
  if (!API_BASE) throw new ApiError("VITE_API_BASE_URL is not configured.", 503, "CONFIGURATION_ERROR");
  const token = await getAccessToken();
  if (!token) throw new ApiError("Your session has expired. Sign in again.", 401, "UNAUTHORIZED");
  const headers = { Authorization: "Bearer " + token, ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
  const response = await fetch(API_BASE + path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(data?.error?.message || "The request could not be completed.", response.status, data?.error?.code || "API_ERROR");
  }
  return data;
}

export async function getCurrentEmployee() {
  const data = await request("/me");
  return data.employee;
}
export async function createEmployee(payload) {
  const data = await request("/employees", { method: "POST", body: JSON.stringify(payload) });
  return data.employee;
}
export async function listEmployees() {
  const data = await request("/employees");
  return (data.employees || []).map((employee) => ({ ...employee, stages: employee.progress?.stages || [] }));
}
export async function getEmployee(employeeId) {
  const data = await request("/employees/" + encodeURIComponent(employeeId));
  return data.employee;
}
export async function getProgress(employeeId) {
  const data = await request("/employees/" + encodeURIComponent(employeeId) + "/progress");
  return data.stages || [];
}
export async function listDocuments(employeeId) {
  const data = await request("/employees/" + encodeURIComponent(employeeId) + "/documents");
  // WP3's public response uses document_type; the portal components use doc_type.
  // Normalize at the API boundary so upload controls always receive a known type.
  return (data.documents || []).map((document) => ({
    ...document,
    doc_type: document.doc_type || document.document_type,
  }));
}
export async function requestUploadUrl(employeeId, document) {
  const data = await request("/employees/" + encodeURIComponent(employeeId) + "/documents/upload-url", {
    method: "POST",
    body: JSON.stringify({
      document_type: document.doc_type,
      content_type: document.content_type,
      file_size: document.file_size,
    }),
  });
  return data;
}
export async function uploadToUrl(employeeId, docType, file, uploadUrl) {
  if (!uploadUrl) throw new ApiError("The upload URL is missing. Request a new one.", 400);
  const response = await fetch(uploadUrl, { method: "PUT", headers: { "Content-Type": file.type }, body: file });
  if (!response.ok) throw new ApiError("S3 rejected the upload. Request a new upload URL and try again.", response.status, "S3_UPLOAD_FAILED");
  return { ok: true };
}
export async function signPolicies(employeeId, policy) {
  return request("/employees/" + encodeURIComponent(employeeId) + "/policies/sign", {
    method: "POST",
    body: JSON.stringify(policy),
  });
}
export async function completeStage(employeeId, stage) {
  return request("/employees/" + encodeURIComponent(employeeId) + "/stages/" + encodeURIComponent(stage) + "/complete", {
    method: "POST",
    body: JSON.stringify({}),
  });
}
