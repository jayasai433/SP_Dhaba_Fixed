import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { SKELETON_KEYS } from "@/lib/skeletons";
import { toast } from "sonner";
import { Trash2, TrendingDown } from "lucide-react";
import { inr, fmtDate, todayIST } from "@/lib/format";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

export default function Wastage() {
  const { user } = useAuth();
  const canAdd = ["admin", "staff"].includes(user.role);

  const [items, setItems]   = useState([]);
  const [reasons, setReasons] = useState([]);
  const [rows, setRows]     = useState(null);
  const [summary, setSummary] = useState(null);

  const [itemId, setItemId] = useState("");
  const [date, setDate]     = useState(todayIST());
  const [qty, setQty]       = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes]   = useState("");
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([
        api.get("/wastage"),
        api.get("/wastage/summary"),
      ]);
      setRows(r.data); setSummary(s.data);
    } catch (err) { setRows([]); toast.error(formatApiError(err)); }
  }, []);

  useEffect(() => {
    api.get("/items").then(({ data }) => setItems(data.filter((i) => i.is_active))).catch(() => {});
    api.get("/wastage/reasons").then(({ data }) => setReasons(data)).catch(() => setReasons([]));
    load();
  }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    const next = {};
    if (!itemId)              next.item   = "Select an item";
    if (!(parseFloat(qty) > 0)) next.qty  = "Quantity must be greater than 0";
    if (!reason)              next.reason = "Select a reason";
    setErrors(next);
    if (Object.keys(next).length) { toast.error(Object.values(next)[0]); return; }
    setSaving(true);
    try {
      await api.post("/wastage", {
        item_id: itemId, date, quantity: parseFloat(qty), reason, notes,
      });
      toast.success("Wastage recorded");
      setItemId(""); setQty(""); setReason(""); setNotes(""); setErrors({});
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  };

  const SummaryCard = ({ label, data, testid }) => (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid={testid}>
      <CardContent className="p-4">
        <div className="text-[10px] font-semibold tracking-widest uppercase text-slate-500">{label}</div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-display font-bold text-2xl text-slate-900 tabular-nums">{inr(data?.cost || 0)}</span>
        </div>
        <div className="text-xs text-slate-500 mt-1 tabular-nums">{data?.count || 0} entries</div>
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6 animate-fade-up" data-testid="wastage-page">
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Operations</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Wastage Log</h1>
        <p className="text-slate-600 text-sm mt-1">Record intentional wastage with a reason — feeds into P&L cost analysis.</p>
      </div>

      {/* Summary KPIs */}
      {summary ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <SummaryCard label="Today"      data={summary.today}    testid="wastage-summary-today" />
          <SummaryCard label="This Week"  data={summary.week}     testid="wastage-summary-week" />
          <SummaryCard label="This Month" data={summary.month}    testid="wastage-summary-month" />
          <SummaryCard label="All Time"   data={summary.all_time} testid="wastage-summary-all" />
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {SKELETON_KEYS.slice(0, 4).map((k) => <Skeleton key={k} className="h-24 rounded-2xl" />)}
        </div>
      )}

      {/* Form */}
      {canAdd && (
        <Card className="rounded-2xl border-orange-900/10 shadow-sm">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-3 flex items-center gap-2">
              <TrendingDown size={18} className="text-orange-600" />Record Wastage
            </h3>
            <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-12 gap-3 items-start">
              <div className="md:col-span-4">
                <Label className="text-sm mb-1.5 block">Item</Label>
                <Select value={itemId} onValueChange={(v) => { setItemId(v); setErrors((p) => ({ ...p, item: undefined })); }}>
                  <SelectTrigger data-testid="wastage-item-select"
                    className={cn("h-11 bg-white", errors.item && "border-red-500")}>
                    <SelectValue placeholder="Select item" />
                  </SelectTrigger>
                  <SelectContent>
                    {items.map((i) => <SelectItem key={i.id} value={i.id}>{i.name} <span className="text-slate-400 text-xs ml-1">({i.unit})</span></SelectItem>)}
                  </SelectContent>
                </Select>
                <div className="h-4 text-[11px] text-red-600 mt-0.5">{errors.item || ""}</div>
              </div>
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">Date</Label>
                <Input type="date" max={todayIST()} value={date} onChange={(e) => setDate(e.target.value)}
                  data-testid="wastage-date-input" className="h-11 bg-white" />
                <div className="h-4" />
              </div>
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">Quantity</Label>
                <Input type="number" min="0" step="0.01" value={qty}
                  onChange={(e) => { setQty(e.target.value); setErrors((p) => ({ ...p, qty: undefined })); }}
                  data-testid="wastage-qty-input"
                  className={cn("h-11 bg-white tabular-nums", errors.qty && "border-red-500")}
                  placeholder="0" />
                <div className="h-4 text-[11px] text-red-600 mt-0.5">{errors.qty || ""}</div>
              </div>
              <div className="md:col-span-4">
                <Label className="text-sm mb-1.5 block">Reason</Label>
                <Select value={reason} onValueChange={(v) => { setReason(v); setErrors((p) => ({ ...p, reason: undefined })); }}>
                  <SelectTrigger data-testid="wastage-reason-select"
                    className={cn("h-11 bg-white", errors.reason && "border-red-500")}>
                    <SelectValue placeholder="Select reason" />
                  </SelectTrigger>
                  <SelectContent>
                    {reasons.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                  </SelectContent>
                </Select>
                <div className="h-4 text-[11px] text-red-600 mt-0.5">{errors.reason || ""}</div>
              </div>
              <div className="md:col-span-12">
                <Label className="text-sm mb-1.5 block">Notes (optional)</Label>
                <Textarea data-testid="wastage-notes-input" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="bg-white" />
              </div>
              <div className="md:col-span-12">
                <Button type="submit" disabled={saving} data-testid="wastage-submit-button"
                  className="rounded-full bg-orange-600 hover:bg-orange-700 px-6 active:scale-95">
                  {saving ? "Saving..." : "Record Wastage"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* History */}
      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <h3 className="font-display text-lg font-semibold text-slate-900 mb-3">Wastage History</h3>
          {rows === null ? (
            <div className="space-y-2">{SKELETON_KEYS.slice(0, 5).map((k) => <Skeleton key={k} className="h-10 rounded-lg" />)}</div>
          ) : rows.length === 0 ? (
            <div className="text-center py-10 text-slate-500">
              <Trash2 className="mx-auto text-orange-300 mb-2" size={36} />
              <p className="font-medium">No wastage recorded yet</p>
              <p className="text-sm mt-1">Every spoilage or breakage you log makes your P&L more accurate.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Item</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead className="text-right">Cost (est.)</TableHead>
                    <TableHead>By</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id} data-testid={`wastage-row-${r.id}`}>
                      <TableCell className="tabular-nums">{fmtDate(r.date)}</TableCell>
                      <TableCell className="font-medium">{r.item_name}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.quantity} {r.unit}</TableCell>
                      <TableCell><span className="text-xs px-2 py-0.5 rounded-full bg-orange-50 text-orange-800 border border-orange-200">{r.reason}</span></TableCell>
                      <TableCell className="text-right tabular-nums font-semibold text-red-700">{inr(r.cost_estimate)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{r.created_by_name}</TableCell>
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
