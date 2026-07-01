import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Token in localStorage since backend and frontend may sit on different
// domains. Same host? httpOnly cookie set by the backend is still respected.
export function getToken()   { return localStorage.getItem("sp_token"); }
export function setToken(t)  { localStorage.setItem("sp_token", t); }
export function clearToken() { localStorage.removeItem("sp_token"); }

const api = axios.create({ baseURL: API, timeout: 15000 });

api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

// Retry only idempotent methods on transient failures. Retrying POSTs risks
// duplicate writes even though the backend has a 10s dedupe window.
const IDEMPOTENT = new Set(["get", "head", "options"]);

async function retryRequest(err) {
  const config = err.config;
  if (!config) return Promise.reject(err);
  const method = (config.method || "get").toLowerCase();
  if (!IDEMPOTENT.has(method)) return Promise.reject(err);
  const isNetwork = !err.response;
  const is5xx    = err.response?.status >= 500;
  if (!isNetwork && !is5xx) return Promise.reject(err);
  config.__retryCount = config.__retryCount || 0;
  if (config.__retryCount >= 2) return Promise.reject(err);
  config.__retryCount++;
  await new Promise((r) => setTimeout(r, config.__retryCount * 1000));
  return api(config);
}

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err.response?.status === 401) {
      if (window.location.pathname !== "/login") {
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
