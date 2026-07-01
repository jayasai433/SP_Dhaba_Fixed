import { useEffect, useMemo, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { inr, fmtDate, todayIST } from "@/lib/format";
import { IndianRupee, AlertTriangle, CheckCircle2, Receipt } from "lucide-react";

export default function Sales() {
  const { user } = useAuth();
  const canEdit = user?.role === "admin";
  const canAdd = ["admin", "staff"].includes(user?.role);

  const [rows, setRows] = useState(null);
  const [date, setDate] = useState(todayIST());
  const [lunch, setLunch]   = useState("");
  const [dinner, setDinner] = useState("");
  const [other, setOther]   = useState("");
  const [notes, setNotes]   = useState("");
  const [duplicate, setDuplicate] = useState(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await api.get("/sales"); setRows(data); } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!date) return setDuplicate(null);
    api.get(`/sales/check/${date}`)
      .then(({ data }) => setDuplicate(data.exists ? data.entry : null))
      .catch(() => setDuplicate(null));
  }, [date]);

  const total = (parseFloat(lunch || 0) + parseFloat(dinner || 0) + parseFloat(other || 0)) || 0;

  const save = async (e) => {
    e.preventDefault();
    if (total <= 0) return toast.error("Enter at least one amount greater than 0");
    setSaving(true);
    try {
      const body = {
        date,
        lunch_amount: parseFloat(lunch || 0),
        dinner_amount: parseFloat(dinner || 0),
        other_amount: parseFloat(other || 0),
        notes: notes || "",
      };
      if (editing && duplicate?.id) {
        await api.patch(`/sales/${duplicate.id}`, body);
        toast.success("Sales updated");
      } else {
        await api.post("/sales", body);
        toast.success("Sales saved");
      }
      setLunch(""); setDinner(""); setOther(""); setNotes(""); setEditing(false);
      load();
      const { data } = await api.get(`/sales/check/${date}`);
      setDuplicate(data.exists ? data.entry : null);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const { dayAmount, weekly, monthly, allTime } = useMemo(() => {
    if (!rows) return { dayAmount: 0, weekly: 0, monthly: 0, allTime: 0 };
    const today = todayIST();
    const start = new Date(today + "T00:00:00"); start.setDate(start.getDate() - 6);
    const weekStart = start.toISOString().slice(0, 10);
    const monthStart = today.slice(0, 7) + "-01";
    let d = 0, w = 0, m = 0, a = 0;
    rows.forEach((r) => {
      a += r.total_amount;
      if (r.date === today)      d += r.total_amount;
      if (r.date >= weekStart)   w += r.total_amount;
      if (r.date >= monthStart)  m += r.total_amount;
    });
    return { dayAmount: d, weekly: w, monthly: m, allTime: a };
  }, [rows]);

  return (
    <div className="space-y-5 animate-fade-up" data-testid="sales-page">
      {/* Header + sticky KPI row */}
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Revenue</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Sales</h1>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
          <Kpi label="Today"      value={dayAmount} highlight testid="sales-today-card" />
          <Kpi label="This week"  value={weekly}    testid="sales-weekly-card" />
          <Kpi label="This month" value={monthly}   testid="sales-monthly-card" />
          <Kpi label="All time"   value={allTime}   testid="sales-alltime-card" />
        </div>
      </div>

      {canAdd && (
        <Card className="rounded-2xl border-orange-900/10 shadow-sm">
          <CardContent className="p-4 md:p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-3">
              {editing ? "Update sales" : "Record sales"}
            </h3>
            <form onSubmit={save} className="space-y-3">
              <div>
                <Label className="text-sm mb-1.5 block">Date</Label>
                <Input type="date" value={date} max={todayIST()}
                  onChange={(e) => setDate(e.target.value)} className="h-11 bg-white"
                  data-testid="sales-date-input" />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <Label className="text-sm mb-1.5 block">Lunch (₹)</Label>
                  <Input type="number" step="0.01" min="0" inputMode="decimal"
                    value={lunch} onChange={(e) => setLunch(e.target.value)}
                    placeholder="0" className="h-11 bg-white tabular-nums text-lg"
                    data-testid="sales-lunch-input" />
                </div>
                <div>
                  <Label className="text-sm mb-1.5 block">Dinner (₹)</Label>
                  <Input type="number" step="0.01" min="0" inputMode="decimal"
                    value={dinner} onChange={(e) => setDinner(e.target.value)}
                    placeholder="0" className="h-11 bg-white tabular-nums text-lg"
                    data-testid="sales-dinner-input" />
                </div>
                <div>
                  <Label className="text-sm mb-1.5 block">Other (₹)</Label>
                  <Input type="number" step="0.01" min="0" inputMode="decimal"
                    value={other} onChange={(e) => setOther(e.target.value)}
                    placeholder="0" className="h-11 bg-white tabular-nums text-lg"
                    data-testid="sales-other-input" />
                </div>
              </div>

              <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-orange-50 border border-orange-100">
                <div className="text-sm text-slate-600">Total</div>
                <div className="font-display font-bold text-2xl text-orange-700 tabular-nums flex items-center"
                     data-testid="sales-total-preview">
                  <IndianRupee size={18} className="mr-0.5" />
                  {total.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                </div>
              </div>

              <div>
                <Label className="text-sm mb-1.5 block">Notes (optional)</Label>
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)}
                  rows={2} className="bg-white" data-testid="sales-notes-input" />
              </div>

              {duplicate && !editing && (
                canEdit ? (
                  <div className="p-3 rounded-xl border text-sm flex items-center gap-2 flex-wrap"
                    style={{ background: "#FFFDE7", borderColor: "#F9A825", color: "#5D4037" }}
                    data-testid="sales-duplicate-warning">
                    <AlertTriangle size={16} style={{ color: "#F57F17" }} />
                    Sales already recorded for <strong>{fmtDate(date)}</strong>. Total: <strong>{inr(duplicate.total_amount)}</strong>.
                    <button type="button" onClick={() => {
                      setLunch(String(duplicate.lunch_amount || 0));
                      setDinner(String(duplicate.dinner_amount || 0));
                      setOther(String(duplicate.other_amount || 0));
                      setNotes(duplicate.notes || "");
                      setEditing(true);
                    }} className="ml-2 underline text-orange-700 font-medium">
                      Edit and correct
                    </button>
                  </div>
                ) : (
                  <div className="p-3 rounded-xl border text-sm flex items-start gap-2"
                    style={{ background: "#E8F5E9", borderColor: "#A5D6A7", color: "#2E7D32" }}
                    data-testid="sales-already-saved">
                    <CheckCircle2 size={16} className="flex-shrink-0 mt-0.5" />
                    <span>
                      Sales for <strong>{fmtDate(date)}</strong> already saved.
                      Total <strong>{inr(duplicate.total_amount)}</strong>. Contact admin for corrections.
                    </span>
                  </div>
                )
              )}

              <div className="flex gap-2">
                <Button type="submit" disabled={saving || (!!duplicate && !editing)}
                  data-testid="sales-submit-button"
                  className="flex-1 h-12 rounded-full bg-orange-600 hover:bg-orange-700 text-base font-medium active:scale-[0.98]">
                  {saving ? "Saving..." : editing ? "Update sales" : "Save sales"}
                </Button>
                {editing && (
                  <Button type="button" variant="outline"
                    onClick={() => { setEditing(false); setLunch(""); setDinner(""); setOther(""); setNotes(""); }}
                    className="h-12 rounded-full">
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-4 md:p-5">
          <h3 className="font-display text-lg font-semibold text-slate-900 mb-3">History</h3>
          {rows === null ? (
            <div className="py-8 text-center text-sm text-slate-400">Loading...</div>
          ) : rows.length === 0 ? (
            <div className="text-center py-10 text-slate-500" data-testid="sales-empty-state">
              <Receipt className="mx-auto text-orange-300 mb-2" size={36} />
              <p className="font-medium">No sales yet today</p>
              <p className="text-sm mt-1">Use the form above to record the first entry.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead className="text-right">Lunch</TableHead>
                    <TableHead className="text-right">Dinner</TableHead>
                    <TableHead className="text-right">Other</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead>Notes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id} data-testid={`sales-row-${r.id}`}>
                      <TableCell className="tabular-nums">{fmtDate(r.date)}</TableCell>
                      <TableCell className="text-right tabular-nums">{inr(r.lunch_amount)}</TableCell>
                      <TableCell className="text-right tabular-nums">{inr(r.dinner_amount)}</TableCell>
                      <TableCell className="text-right tabular-nums">{inr(r.other_amount)}</TableCell>
                      <TableCell className="text-right tabular-nums font-semibold">{inr(r.total_amount)}</TableCell>
                      <TableCell className="text-sm text-slate-500">{r.notes || "."}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Kpi({ label, value, highlight, testid }) {
  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid={testid}>
      <CardContent className="p-3 md:p-4">
        <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
        <div className={`font-display font-bold text-xl md:text-2xl tabular-nums ${highlight ? "text-orange-700" : "text-slate-900"}`}>
          {inr(value)}
        </div>
      </CardContent>
    </Card>
  );
}
