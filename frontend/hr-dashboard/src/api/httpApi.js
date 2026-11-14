import {getAccessToken} from "../auth.js";
const API_BASE=(import.meta.env.VITE_API_BASE_URL||"").replace(/\/$/,"");
export class ApiError extends Error{constructor(message,status=500,code="API_ERROR"){super(message);this.name="ApiError";this.status=status;this.code=code;}}
async function request(path,options={}){if(!API_BASE)throw new ApiError("VITE_API_BASE_URL is not configured.",503,"CONFIGURATION_ERROR");const token=await getAccessToken();if(!token)throw new ApiError("Your session has expired. Sign in again.",401,"UNAUTHORIZED");const headers={Authorization:"Bearer "+token,...(options.body?{"Content-Type":"application/json"}:{}),...(options.headers||{})};const response=await fetch(API_BASE+path,{...options,headers});const data=await response.json().catch(()=>({}));if(!response.ok)throw new ApiError(data?.error?.message||"The request could not be completed.",response.status,data?.error?.code||"API_ERROR");return data;}
export async function getCurrentEmployee(){return (await request("/me")).employee;}
export async function createEmployee(payload){return (await request("/employees",{method:"POST",body:JSON.stringify(payload)})).employee;}
export async function listEmployees(){const data=await request("/employees");return(data.employees||[]).map(e=>({...e,stages:e.progress?.stages||[]}));}
export async function getEmployee(id){return(await request("/employees/"+encodeURIComponent(id))).employee;}
export async function getProgress(id){return(await request("/employees/"+encodeURIComponent(id)+"/progress")).stages||[];}
export async function listDocuments(id){return(await request("/employees/"+encodeURIComponent(id)+"/documents")).documents||[];}
export async function requestUploadUrl(id,doc){return request("/employees/"+encodeURIComponent(id)+"/documents/upload-url",{method:"POST",body:JSON.stringify({document_type:doc.doc_type,content_type:doc.content_type,file_size:doc.file_size})});}
export async function uploadToUrl(id,type,file,url){if(!url)throw new ApiError("The upload URL is missing.",400);const response=await fetch(url,{method:"PUT",headers:{"Content-Type":file.type},body:file});if(!response.ok)throw new ApiError("S3 rejected the upload. Request a new URL and try again.",response.status,"S3_UPLOAD_FAILED");return{ok:true};}
export async function signPolicies(id,policy){return request("/employees/"+encodeURIComponent(id)+"/policies/sign",{method:"POST",body:JSON.stringify(policy)});}
export async function completeStage(id,stage){return request("/employees/"+encodeURIComponent(id)+"/stages/"+encodeURIComponent(stage)+"/complete",{method:"POST",body:JSON.stringify({})});}
