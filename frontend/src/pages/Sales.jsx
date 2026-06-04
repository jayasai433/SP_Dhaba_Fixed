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
import { IndianRupee, AlertTriangle } from "lucide-react";
import { useSave } from "@/hooks/useSave";

export default function Sales() {
  const [rows, setRows] = useState([]);
  const [date, setDate] = useState(todayIST());
  const [lunch, setLunch] = useState("");
  const [dinner, setDinner] = useState("");
  const [other, setOther] = useState("");
  const [notes, setNotes] = useState("");
  const [duplicate, setDuplicate] = useState(null);
  const [editing, setEditing] = useState(false);
  const [saving2, setSaving2] = useState(false);
  const { user } = useAuth();
  const canEdit = user?.role === "admin";

  const load = useCallback(() => { api.get("/sales").then(({ data }) => setRows(data)).catch((err) => console.error(err)); }, []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!date) return setDuplicate(null);
    api.get(`/sales/check/${date}`).then(({ data }) => setDuplicate(data.exists ? data.entry : null)).catch(() => setDuplicate(null));
  }, [date]);

  const total = (parseFloat(lunch || 0) + parseFloat(dinner || 0) + parseFloat(other || 0)) || 0;

  const { save, saving } = useSave(
    () => api.post("/sales", {
      date,
      lunch_amount: parseFloat(lunch || 0),
      dinner_amount: parseFloat(dinner || 0),
      other_amount: parseFloat(other || 0),
      notes: notes || "",
    }),
    { successMessage: "Sales saved", onSuccess: () => { setLunch(""); setDinner(""); setOther(""); setNotes(""); load(); } }
  );

  const updateSales = async (e) => {
    e.preventDefault();
    if (!duplicate?.id) return;
    setSaving2(true);
    try {
      await api.patch(`/sales/${duplicate.id}`, {
        date,
        lunch_amount: parseFloat(lunch || 0),
        dinner_amount: parseFloat(dinner || 0),
        other_amount: parseFloat(other || 0),
        notes: notes || "",
      });
      toast.success("Sales entry updated successfully");
      setEditing(false);
      setLunch(""); setDinner(""); setOther(""); setNotes("");
      load();
      api.get(`/sales/check/${date}`).then(({ data }) => setDuplicate(data.exists ? data.entry : null)).catch(() => setDuplicate(null));
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving2(false); }
  };

  const submit = (e) => {
    e.preventDefault();
    if (duplicate) {
      if (!window.confirm(`Sales already saved for ${fmtDate(date)}. Cannot add again.`)) return;
      return;
    }
    save();
  };

  const { weekly, monthly } = useMemo(() => {
    const today = new Date(todayIST() + "T00:00:00");
    const weekAgo = new Date(today); weekAgo.setDate(today.getDate() - 6);
    const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
    let w = 0, m = 0;
    rows.forEach((r) => {
      const d = new Date(r.date + "T00:00:00");
      if (d >= weekAgo && d <= today) w += r.total_amount;
      if (d >= monthStart && d <= today) m += r.total_amount;
    });
    return { weekly: w, monthly: m };
  }, [rows]);

  return (
    <div className="space-y-6 animate-fade-up" data-testid="sales-page">
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Revenue</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Sales</h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="sales-weekly-card">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-slate-500">This Week</div>
            <div className="font-display font-bold text-2xl text-slate-900 tabular-nums">{inr(weekly)}</div>
          </CardContent>
        </Card>
        <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid="sales-monthly-card">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-slate-500">This Month</div>
            <div className="font-display font-bold text-2xl text-slate-900 tabular-nums">{inr(monthly)}</div>
          </CardContent>
        </Card>
        <Card className="rounded-2xl border-orange-900/10 shadow-sm col-span-2 md:col-span-1" data-testid="sales-alltime-card">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-slate-500">All-Time</div>
            <div className="font-display font-bold text-2xl text-orange-700 tabular-nums">{inr(rows.reduce((a, b) => a + b.total_amount, 0))}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <h3 className="font-display text-lg font-semibold text-slate-900 mb-4">Record Sales</h3>
          <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
            <div className="md:col-span-3">
              <Label className="text-sm mb-1.5 block">Date</Label>
              <Input type="date" data-testid="sales-date-input" value={date} onChange={(e) => setDate(e.target.value)} className="h-11 bg-white" />
            </div>
            <div className="md:col-span-2">
              <Label className="text-sm mb-1.5 block">Lunch (₹)</Label>
              <Input type="number" step="0.01" min="0" data-testid="sales-lunch-input" value={lunch} onChange={(e) => setLunch(e.target.value)} className="h-11 bg-white tabular-nums" placeholder="0" />
            </div>
            <div className="md:col-span-2">
              <Label className="text-sm mb-1.5 block">Dinner (₹)</Label>
              <Input type="number" step="0.01" min="0" data-testid="sales-dinner-input" value={dinner} onChange={(e) => setDinner(e.target.value)} className="h-11 bg-white tabular-nums" placeholder="0" />
            </div>
            <div className="md:col-span-2">
              <Label className="text-sm mb-1.5 block">Other (₹)</Label>
              <Input type="number" step="0.01" min="0" data-testid="sales-other-input" value={other} onChange={(e) => setOther(e.target.value)} className="h-11 bg-white tabular-nums" placeholder="0" />
            </div>
            <div className="md:col-span-3">
              <Label className="text-sm mb-1.5 block">Total</Label>
              <div className="h-11 px-3 rounded-lg bg-orange-50 border border-orange-200 flex items-center font-bold text-orange-700 tabular-nums text-lg" data-testid="sales-total-preview">
                <IndianRupee size={16} className="mr-0.5" />{total.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
              </div>
            </div>
            <div className="md:col-span-12">
              <Label className="text-sm mb-1.5 block">Notes (optional)</Label>
              <Textarea data-testid="sales-notes-input" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="bg-white" />
            </div>
            {duplicate && !editing && (
              <div className="md:col-span-12 p-3 rounded-xl bg-amber-50 border border-amber-300 text-sm text-amber-900 flex items-center gap-2 flex-wrap" data-testid="duplicate-warning">
                <AlertTriangle size={16} />
                Sales already recorded for <b>{fmtDate(date)}</b> ({inr(duplicate.total_amount)}).
                {canEdit && (
                  <button type="button" onClick={() => {
                    setLunch(String(duplicate.lunch_amount || 0));
                    setDinner(String(duplicate.dinner_amount || 0));
                    setOther(String(duplicate.other_amount || 0));
                    setNotes(duplicate.notes || "");
                    setEditing(true);
                  }} className="ml-2 underline text-orange-700 font-medium">
                    Edit & Correct
                  </button>
                )}
                {!canEdit && " Choose another date."}
              </div>
            )}
            <div className="md:col-span-12">
              <div className="flex gap-2">
                <Button type="submit" onClick={editing ? updateSales : undefined} disabled={saving || saving2 || (!!duplicate && !editing)} data-testid="sales-submit-button"
                  className="rounded-full bg-orange-600 hover:bg-orange-700 px-6 active:scale-95">
                  {(saving || saving2) ? "Saving..." : editing ? "Update Sales" : "Save Sales"}
                </Button>
                {editing && (
                  <Button type="button" variant="outline" onClick={() => { setEditing(false); setLunch(""); setDinner(""); setOther(""); setNotes(""); }}
                    className="rounded-full border-orange-200 text-orange-700">
                    Cancel
                  </Button>
                )}
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <h3 className="font-display text-lg font-semibold text-slate-900 mb-3">Sales History</h3>
          {rows.length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">No sales recorded yet.</p>
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
                      <TableCell className="text-sm text-slate-500">{r.notes || "—"}</TableCell>
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
