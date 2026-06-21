/**
 * useClosingStock — Custom hook for closing stock operations.
 *
 * Separation of concerns:
 *   - This hook owns all API calls for closing stock
 *   - ClosingStock.jsx just calls this hook — no API logic in page
 *   - Easy to test, easy to extend (add offline support, caching etc.)
 */

import { useState, useCallback } from "react";
import logger from "@/lib/logger";
import { toast } from "sonner";
import api, { formatApiError } from "@/lib/api";

export function useClosingStock() {
  const [saving, setSaving]   = useState(false);
  const [loading, setLoading] = useState(false);
  const [entries, setEntries] = useState([]);
  // summary intentionally removed — wastage analysis requires recipe mapping first

  /** Record physical shelf count for one item */
  const recordCount = useCallback(async (payload) => {
    setSaving(true);
    try {
      const { data } = await api.post("/closing-stock", payload);
      toast.success(
        data.wastage_flag
          ? `⚠️ High variance on ${data.item_name} — ${data.variance_pct}% discrepancy`
          : `✅ ${data.item_name}: ${data.closing_qty} ${data.unit} recorded`
      );
      return data;
    } catch (err) {
      toast.error(formatApiError(err, "Failed to save count"));
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  /** Load all entries for a given date */
  const loadByDate = useCallback(async (dateStr) => {
    setLoading(true);
    try {
      const { data } = await api.get(`/closing-stock/${dateStr}`);
      setEntries(data);
    } catch (err) {
      logger.error("Failed to load closing stock:", err);
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  return { saving, loading, entries, recordCount, loadByDate };
}
