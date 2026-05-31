import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const BusinessProfileContext = createContext({
  profile: { name: "SP Royal Punjabi Dhaba", logo_base64: "", address: "", phone: "" },
  refresh: () => {},
});

export function BusinessProfileProvider({ children }) {
  const [profile, setProfile] = useState({
    name: "SP Royal Punjabi Dhaba", logo_base64: "", address: "", phone: "",
  });

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/business-profile");
      if (data && data.name) setProfile(data);
    } catch { /* not logged in yet */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <BusinessProfileContext.Provider value={{ profile, refresh }}>
      {children}
    </BusinessProfileContext.Provider>
  );
}

export const useBusinessProfile = () => useContext(BusinessProfileContext);
