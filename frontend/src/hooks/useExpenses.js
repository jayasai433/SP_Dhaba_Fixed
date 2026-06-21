/**
 * useExpenses — data layer for the Expenses page.
 */
import { useEffect, useState, useCallback, useMemo } from "react";
import api, { formatApiError } from "@/lib/api";
import logger from "@/lib/logger";
import { toast } from "sonner";
import { todayIST } from "@/lib/format";
import { useSave } from "@/hooks/useSave";
import { useDateFilter } from "@/hooks/useDateFilter";

export function useExpenses() {
  const [cats, setCats]           = useState([]);
  const [rows, setRows]           = useState(null);
  const [filterCat, setFilterCat] = useState("all");
  const [voidDialogId, setVoidDialogId] = useState(null);
  const [date, setDate]           = useState(todayIST());
  const [cat, setCat]             = useState("");
  const [desc, setDesc]           = useState("");
  const [amt, setAmt]             = useState("");
  const { start, end, setStart, setEnd, dateParams } = useDateFilter();

  useEffect(() => {
    api.get("/expense-categories")
      .then(({ data }) => setCats(data))
      .catch((err) => logger.error("Expense categories load failed:", err));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const load = useCallback(() => {
    const q = { ...dateParams, ...(filterCat !== "all" ? { category: filterCat } : {}) };
    api.get("/expenses", { params: q })
      .then(({ data }) => setRows(data))
      .catch((err) => logger.error("Expenses load failed:", err));
  }, [filterCat, dateParams]);

  useEffect(() => { load(); }, [load]);

  const { save, saving, dupDialog, confirmDuplicate, cancelDuplicate } = useSave(
    () => api.post("/expenses", { date, category: cat, description: desc, amount: parseFloat(amt) }),
    { successMessage: "Expense saved", onSuccess: () => { setDesc(""); setAmt(""); load(); } }
  );

  const [anomalyWarnings, setAnomalyWarnings] = useState([]);
  const [anomalySeverity, setAnomalySeverity] = useState('warning');
  const [anomalyDialog, setAnomalyDialog] = useState(false);

  const validateAndSave = async (e) => {
    e.preventDefault();
    if (!cat) return toast.error("Select a category");
    if (!(parseFloat(amt) > 0)) return toast.error("Amount must be greater than 0");

    // Anomaly check before saving
    try {
      const { data } = await api.post("/anomaly-check", {
        entry_type: "expense",
        category: cat,
        description: desc,
        total_amount: parseFloat(amt),
      });
      if (data.is_suspicious) {
        setAnomalyWarnings(data.warnings);
        setAnomalySeverity(data.severity);
        setAnomalyDialog(true);
        return;
      }
    } catch { /* anomaly check failed — save normally */ }
    save();
  };

  const confirmAnomaly = () => { setAnomalyDialog(false); save(); };
  const cancelAnomaly  = () => { setAnomalyDialog(false); };

  const handleVoidConfirm = async (reason) => {
    const id = voidDialogId;
    setVoidDialogId(null);
    try {
      await api.patch(`/expenses/${id}/void`, { reason });
      toast.success("Entry voided");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const { dayTotal, weekTotal, monthTotal } = useMemo(() => {
    if (!rows) return { dayTotal: 0, weekTotal: 0, monthTotal: 0 };
    const today = todayIST();
    const start7 = new Date(today + "T00:00:00"); start7.setDate(start7.getDate() - 6);
    const monthStart = today.slice(0, 7) + "-01";
    let d = 0, w = 0, m = 0;
    rows.forEach((r) => {
      if (r.is_void) return;
      if (r.date === today)                 d += r.amount;
      if (r.date >= start7.toISOString().slice(0, 10)) w += r.amount;
      if (r.date >= monthStart)             m += r.amount;
    });
    return { dayTotal: d, weekTotal: w, monthTotal: m };
  }, [rows]);

  return {
    cats, rows, filterCat, setFilterCat,
    start, end, setStart, setEnd, dateParams,
    date, setDate, cat, setCat, desc, setDesc, amt, setAmt,
    dayTotal, weekTotal, monthTotal,
    validateAndSave, saving, load,
    dupDialog, confirmDuplicate, cancelDuplicate,
    voidDialogId, setVoidDialogId, handleVoidConfirm,
    anomalyWarnings, anomalySeverity, anomalyDialog, confirmAnomaly, cancelAnomaly,
  };
}
