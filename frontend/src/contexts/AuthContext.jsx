import { createContext, useContext, useEffect, useRef, useState } from "react";
import api, { setToken, clearToken, getToken } from "@/lib/api";
import { toast } from "sonner";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = sessionStorage.getItem("sp_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    api.get("/auth/me", { signal: controller.signal })
      .then(({ data }) => {
        setUser(data);
        sessionStorage.setItem("sp_user", JSON.stringify(data));
      })
      .catch((err) => {
        if (err.name === "CanceledError") return;
        clearToken();
        sessionStorage.removeItem("sp_user");
        setUser(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  // ── Session expiry warning ───────────────────────────────────────────────
  const _expiryTimerRef  = useRef(null);
  const _warningTimerRef = useRef(null);
  const TOKEN_TTL_MS     = 8 * 60 * 60 * 1000;       // 8 hours (matches backend)
  const WARNING_BEFORE   = 30 * 60 * 1000;            // warn 30 min before expiry

  const _clearExpiryTimers = () => {
    if (_expiryTimerRef.current)  clearTimeout(_expiryTimerRef.current);
    if (_warningTimerRef.current) clearTimeout(_warningTimerRef.current);
  };

  const _scheduleExpiryWarning = (loginTime = Date.now()) => {
    _clearExpiryTimers();
    const elapsed     = Date.now() - loginTime;
    const remaining   = TOKEN_TTL_MS - elapsed;
    const warnIn      = remaining - WARNING_BEFORE;

    if (warnIn > 0) {
      _warningTimerRef.current = setTimeout(() => {
        toast.warning(
          "Your session expires in 30 minutes. Save your work and log in again to continue.",
          { duration: 15000, id: "session-expiry-warning" }
        );
      }, warnIn);
    }

    if (remaining > 0) {
      _expiryTimerRef.current = setTimeout(() => {
        toast.error("Session expired. Please log in again.", { duration: 5000 });
        clearToken();
        sessionStorage.removeItem("sp_user");
        setUser(null);
        window.location.href = "/login";
      }, remaining);
    }
  };

  // Re-schedule on mount if a token already exists (page refresh case)
  useEffect(() => {
    const token = getToken();
    if (token) {
      try {
        // Decode JWT payload (no verification — just for iat claim)
        const payload = JSON.parse(atob(token.split(".")[1]));
        if (payload.iat) _scheduleExpiryWarning(payload.iat * 1000);
      } catch { /* malformed token — let the /auth/me call handle it */ }
    }
    return _clearExpiryTimers;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    // Store token for cross-domain requests (cookie won't work cross-domain)
    if (data.token) setToken(data.token);
    sessionStorage.setItem("sp_user", JSON.stringify(data.user));
    setUser(data.user);
    _scheduleExpiryWarning();   // start the 8h countdown from now
    return data.user;
  };

  const logout = async () => {
    _clearExpiryTimers();
    try { await api.post("/auth/logout"); } catch { /* ignore */ }
    clearToken();
    sessionStorage.removeItem("sp_user");
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
