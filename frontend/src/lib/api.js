import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Token stored in localStorage for cross-domain deployments
// (httpOnly cookie only works same-domain)
export function getToken() {
  return localStorage.getItem("sp_token");
}

export function setToken(token) {
  localStorage.setItem("sp_token", token);
}

export function clearToken() {
  localStorage.removeItem("sp_token");
}

const api = axios.create({ baseURL: API, timeout: 15000 }); // 15s timeout

// Attach token to every request
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Retry helper — retries network errors up to 2 times with backoff
async function retryRequest(err) {
  const config = err.config;
  if (!config) return Promise.reject(err);
  
  // Only retry on network errors or 5xx (not 4xx — those are real errors)
  const isNetworkError = !err.response;
  const is5xx = err.response?.status >= 500;
  if (!isNetworkError && !is5xx) return Promise.reject(err);
  
  config.__retryCount = config.__retryCount || 0;
  if (config.__retryCount >= 2) return Promise.reject(err);
  
  config.__retryCount++;
  const delay = config.__retryCount * 1000; // 1s, 2s backoff
  await new Promise((r) => setTimeout(r, delay));
  return api(config);
}

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err.response?.status === 401) {
      const path = window.location.pathname;
      if (path !== "/login") {
        clearToken();
        sessionStorage.removeItem("sp_user");
        window.location.href = "/login";
      }
      return Promise.reject(err);
    }
    return retryRequest(err);
  }
);

export function formatApiError(err, fallback = "Something went wrong") {
  const d = err?.response?.data?.detail;
  if (!d) return err?.message || fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e.msg || JSON.stringify(e)).join(" ");
  return String(d);
}

export default api;
