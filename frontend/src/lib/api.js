import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// withCredentials sends/receives the httpOnly auth cookie. Token is no longer
// stored in localStorage (XSS-safe). User profile is kept in sessionStorage
// only for fast UI hydration; it carries no secret.
const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      const path = window.location.pathname;
      if (path !== "/login") {
        sessionStorage.removeItem("sp_user");
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
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
