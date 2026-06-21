/**
 * usePurchases — data layer for the Purchases page.
 * Extracts all API calls, state, and side effects out of the component.
 */
import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import logger from "@/lib/logger";
import { toast } from "sonner";
import { todayIST } from "@/lib/format";
import { useSave } from "@/hooks/useSave";
import { useDateFilter } from "@/hooks/useDateFilter";

export function usePurchases() {
  const [params] = useSearchParams();
  const [items, setItems]       = useState([]);
  const [rows, setRows]         = useState(null);
  const [filterItem, setFilterItem] = useState("all");
  const [voidDialogId, setVoidDialogId] = useState(null);
  const [itemId, setItemId]     = useState(params.get("item") || "");
  const [date, setDate]         = useState(todayIST());
  const [qty, setQty]           = useState("");
  const [price, setPrice]       = useState("");
  const [errors, setErrors]     = useState({});
  const { start, end, setStart, setEnd, dateParams } = useDateFilter();

  // Load items once on mount
  useEffect(() => {
    api.get("/items")
      .then(({ data }) => setItems(data))
      .catch((err) => logger.error("Items load failed:", err));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Reload purchases when filters change
  const load = useCallback(() => {
    const q = { ...dateParams, ...(filterItem !== "all" ? { item_id: filterItem } : {}) };
    api.get("/purchases", { params: q })
      .then(({ data }) => setRows(data))
      .catch((err) => logger.error("Purchases load failed:", err));
  }, [filterItem, dateParams]);

  useEffect(() => { load(); }, [load]);

  const [anomalyWarnings, setAnomalyWarnings] = useState([]);
  const [anomalySeverity, setAnomalySeverity] = useState('warning');
  const [anomalyDialog, setAnomalyDialog] = useState(false);
  const [pendingSave, setPendingSave] = useState(false);

  const { save, saving, dupDialog, confirmDuplicate, cancelDuplicate } = useSave(
    () => api.post("/purchases", {
      item_id: itemId, date,
      quantity: parseFloat(qty),
      price_per_unit: parseFloat(price),
    }),
    {
      successMessage: "Purchase saved",
      onSuccess: () => { setQty(""); setPrice(""); setErrors({}); setAnomalyWarnings([]); load(); },
    }
  );

  const validateAndSave = async (e) => {
    e.preventDefault();
    const next = {};
    if (!itemId)                            next.item  = "Please select an item";
    if (!(parseFloat(qty) > 0))             next.qty   = "Quantity must be greater than 0";
    if (!price || !(parseFloat(price) > 0)) next.price = "Price must be greater than ₹0";
    setErrors(next);
    if (Object.keys(next).length) { toast.error(Object.values(next)[0]); return; }

    // Anomaly check before saving
    try {
      const { data } = await api.post("/anomaly-check", {
        entry_type: "purchase",
        item_id: itemId,
        item_name: items.find(i => i.id === itemId)?.name,
        quantity: parseFloat(qty),
        price_per_unit: parseFloat(price),
      });
      if (data.is_suspicious) {
        setAnomalyWarnings(data.warnings);
        setAnomalySeverity(data.severity);
        setAnomalyDialog(true);
        setPendingSave(true);
        return;
      }
    } catch { /* anomaly check failed — save normally */ }
    save();
  };

  const confirmAnomaly = () => { setAnomalyDialog(false); setPendingSave(false); save(); };
  const cancelAnomaly  = () => { setAnomalyDialog(false); setPendingSave(false); };

  const handleVoidConfirm = async (reason) => {
    const id = voidDialogId;
    setVoidDialogId(null);
    try {
      await api.patch(`/purchases/${id}/void`, { reason });
      toast.success("Entry voided");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const selectedItem    = items.find((i) => i.id === itemId);
  const activeItems     = items.filter((i) => i.is_active);
  const total           = (parseFloat(qty || 0) * parseFloat(price || 0)) || 0;
  const runningTotal    = (rows || []).reduce((a, b) => a + (b.total_cost || 0), 0);

  return {
    // Lists
    items, activeItems, rows, selectedItem,
    // Filters
    filterItem, setFilterItem, start, end, setStart, setEnd, dateParams,
    // Form state
    itemId, setItemId, date, setDate, qty, setQty, price, setPrice, errors, setErrors,
    // Derived
    total, runningTotal,
    // Actions
    validateAndSave, saving, load,
    dupDialog, confirmDuplicate, cancelDuplicate,
    voidDialogId, setVoidDialogId, handleVoidConfirm,
    anomalyWarnings, anomalySeverity, anomalyDialog, confirmAnomaly, cancelAnomaly,
  };
}
