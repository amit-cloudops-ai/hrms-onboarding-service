import * as mockApi from "./mockApi.js";
import * as httpApi from "./httpApi.js";

export const useMock = import.meta.env?.VITE_USE_MOCK !== "false";
export const api = useMock ? mockApi : httpApi;
export const ApiError = useMock ? mockApi.ApiError : httpApi.ApiError;
export const mockSettings = mockApi.mockSettings;
export * from "./constants.js";
export { validateUpload } from "./validation.js";
export { MOCK_CURRENT_EMPLOYEE_ID } from "./mockData.js";
