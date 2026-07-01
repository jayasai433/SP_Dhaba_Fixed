import { useEffect, useMemo, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { inr, fmtDate, todayIST } from "@/lib/format";
import { Plus, Wallet, Ban } from "lucide-react";
import VoidDialog from "@/components/VoidDialog";

export default function Expenses() {
  const { user } = useAuth();
  const canAdd = ["admin", "staff"].includes(user?.role);

  const [cats, setCats] = useState([]);
  const [rows, setRows] = useState(null);
  const [filterCat, setFilterCat] = useState("all");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const [date, setDate] = useState(todayIST());
  const [cat, setCat] = useState("");
  const [desc, setDesc] = useState("");
  const [amt, setAmt] = useState("");
  const [saving, setSaving] = useState(false);
  const [voidId, setVoidId] = useState(null);

  const loadCats = useCallback(async () => {
    try { const { data } = await api.get("/expense-categories"); setCats(data); } catch {}
  }, []);

  const loadRows = useCallback(async () => {
    try {
      const params = {
        ...(start ? { start } : {}),
        ...(end   ? { end }   : {}),
        ...(filterCat !== "all" ? { category: filterCat } : {}),
      };
      const { data } = await api.get("/expenses", { params });
      setRows(data);
    } catch {}
  }, [start, end, filterCat]);

  useEffect(() => { loadCats(); }, [loadCats]);
  useEffect(() => { loadRows(); }, [loadRows]);

  const save = async (e) => {
    e.preventDefault();
    if (!cat) return toast.error("Select a category");
    if (!(parseFloat(amt) > 0)) return toast.error("Amount must be greater than 0");
    setSaving(true);
    try {
      await api.post("/expenses", {
        date, category: cat,
        description: desc || "",
        amount: parseFloat(amt),
      });
      toast.success("Expense saved");
      setDesc(""); setAmt("");
      loadRows();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const handleVoidConfirm = async (reason) => {
    const id = voidId; setVoidId(null);
    try { await api.patch(`/expenses/${id}/void`, { reason }); toast.success("Expense voided"); loadRows(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const { dayTotal, weekTotal, monthTotal } = useMemo(() => {
    if (!rows) return { dayTotal: 0, weekTotal: 0, monthTotal: 0 };
    const today = todayIST();
    const s = new Date(today + "T00:00:00"); s.setDate(s.getDate() - 6);
    const weekStart = s.toISOString().slice(0, 10);
    const monthStart = today.slice(0, 7) + "-01";
    let d = 0, w = 0, m = 0;
    rows.forEach((r) => {
      if (r.is_void) return;
      if (r.date === today)     d += r.amount;
      if (r.date >= weekStart)  w += r.amount;
      if (r.date >= monthStart) m += r.amount;
    });
    return { dayTotal: d, weekTotal: w, monthTotal: m };
  }, [rows]);

  return (
    <div className="space-y-5 animate-fade-up" data-testid="expenses-page">
      <VoidDialog open={!!voidId} onConfirm={handleVoidConfirm}
        onCancel={() => setVoidId(null)} entryLabel="expense" />

      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Operating</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Expenses</h1>
        <div className="grid grid-cols-3 gap-3 mt-3">
          <Kpi label="Today"      value={dayTotal}   highlight testid="exp-today-card" />
          <Kpi label="This week"  value={weekTotal}  testid="exp-week-card" />
          <Kpi label="This month" value={monthTotal} testid="exp-month-card" />
        </div>
      </div>

      {canAdd && (
        <Card className="rounded-2xl border-orange-900/10 shadow-sm">
          <CardContent className="p-4 md:p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-3 flex items-center gap-2">
              <Plus size={18} className="text-orange-600" />Add expense
            </h3>
            <form onSubmit={save} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-sm mb-1.5 block">Date</Label>
                  <Input type="date" value={date} max={todayIST()}
                    onChange={(e) => setDate(e.target.value)} className="h-11 bg-white"
                    data-testid="exp-date-input" />
                </div>
                <div>
                  <Label className="text-sm mb-1.5 block">Category</Label>
                  <Select value={cat} onValueChange={setCat}>
                    <SelectTrigger className="h-11 bg-white" data-testid="exp-cat-select">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      {cats.map((c) => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label className="text-sm mb-1.5 block">Description (optional)</Label>
                <Input value={desc} onChange={(e) => setDesc(e.target.value)}
                  placeholder="e.g. Electricity bill" className="h-11 bg-white"
                  data-testid="exp-desc-input" />
              </div>

              <div>
                <Label className="text-sm mb-1.5 block">Amount (₹)</Label>
                <Input type="number" step="0.01" min="0" inputMode="decimal"
                  value={amt} onChange={(e) => setAmt(e.target.value)}
                  placeholder="0" className="h-11 bg-white tabular-nums text-lg"
                  data-testid="exp-amount-input" />
              </div>

              <Button type="submit" disabled={saving} data-testid="exp-submit-button"
                className="w-full h-12 rounded-full bg-orange-600 hover:bg-orange-700 text-base font-medium active:scale-[0.98]">
                {saving ? "Saving..." : "Save expense"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-4 md:p-5">
          <div className="flex flex-col md:flex-row md:items-end gap-3 mb-4">
            <div className="flex-1">
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">Category</Label>
              <Select value={filterCat} onValueChange={setFilterCat}>
                <SelectTrigger className="h-10 bg-white" data-testid="exp-filter-cat">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  {cats.map((c) => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">From</Label>
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)}
                className="h-10 bg-white" data-testid="exp-filter-start" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">To</Label>
              <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
                className="h-10 bg-white" data-testid="exp-filter-end" />
            </div>
          </div>

          {rows === null ? (
            <div className="py-8 text-center text-sm text-slate-400">Loading...</div>
          ) : rows.length === 0 ? (
            <div className="text-center py-10 text-slate-500" data-testid="expenses-empty-state">
              <Wallet className="mx-auto text-orange-300 mb-2" size={36} />
              <p className="font-medium">No expenses yet</p>
              <p className="text-sm mt-1">Add your first entry using the form above.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>By</TableHead>
                    {canAdd && <TableHead></TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id} data-testid={`expense-row-${r.id}`}>
                      <TableCell className="tabular-nums">{fmtDate(r.date)}</TableCell>
                      <TableCell>{r.category}</TableCell>
                      <TableCell className="text-slate-500">{r.description || "."}</TableCell>
                      <TableCell className="text-right tabular-nums font-semibold">{inr(r.amount)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{r.created_by_name}</TableCell>
                      {canAdd && (
                        <TableCell>
                          <button title="Void" onClick={() => setVoidId(r.id)}
                            className="text-red-400 hover:text-red-600 transition-colors"
                            data-testid={`void-expense-${r.id}`}>
                            <Ban size={15} />
                          </button>
                        </TableCell>
                      )}
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
