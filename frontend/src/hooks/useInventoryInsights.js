/**
 * useInventoryInsights — Custom hook for inventory intelligence data.
 *
 * Separation of concerns:
 *   - All API calls live here, never in page components
 *   - Easy to test, mock, extend
 */

import { useState, useCallback } from "react";
import logger from "@/lib/logger";
import api from "@/lib/api";

export function useInventoryInsights() {
  const [loading, setLoading]             = useState(false);
  const [insights, setInsights]           = useState(null);
  const [costTrend, setCostTrend]         = useState([]);
  const [error, setError]                 = useState(false);

  const loadInsights = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const { data } = await api.get("/inventory/insights");
      setInsights(data);
    } catch (err) {
      logger.error("Failed to load inventory insights:", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCostTrend = useCallback(async (days = 30) => {
    try {
      const { data } = await api.get("/inventory/cost-trend", { params: { days } });
      setCostTrend(data);
    } catch (err) {
      logger.error("Failed to load cost trend:", err);
      setCostTrend([]);
    }
  }, []);

  return { loading, error, insights, costTrend, loadInsights, loadCostTrend };
}
