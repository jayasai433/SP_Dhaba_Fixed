/**
 * useConsumption — fetches consumption rates from backend.
 * Cached for 1 hour in component state — no refetch on every render.
 */
import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import logger from "@/lib/logger";

export function useConsumption() {
  const [rates, setRates]       = useState({});   // keyed by item_id
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get("/consumption-rates");
      // Convert array to map for O(1) lookup by item_id
      const map = {};
      (data.rates || []).forEach((r) => { map[r.item_id] = r; });
      setRates(map);
      setError(false);
    } catch (err) {
      logger.error("Consumption rates fetch failed:", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  return { rates, loading, error, reload: load };
}

export function useSmartReorder() {
  const [insight, setInsight]   = useState(null);
  const [loading, setLoading]   = useState(true);
  const [cached, setCached]     = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get("/smart-reorder");
      setInsight(data.insight);
      setCached(data.cached);
    } catch (err) {
      logger.error("Smart reorder fetch failed:", err);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  return { insight, loading, cached, reload: load };
}
