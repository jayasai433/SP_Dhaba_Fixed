import { createContext, useContext, useEffect, useState } from "react";
import api, { setToken, clearToken } from "@/lib/api";

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

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    // Store token for cross-domain requests (cookie won't work cross-domain)
    if (data.token) setToken(data.token);
    sessionStorage.setItem("sp_user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
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
