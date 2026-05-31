import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { fmtDate, fmtTimestamp, todayIST } from "@/lib/format";
import { Plus, X, ChefHat, Ban } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export default function DailyUsage() {
  const { user } = useAuth();
  const canAdd = ["admin", "staff"].includes(user.role);
  const [items, setItems] = useState([]);
  const [stockMap, setStockMap] = useState({});
  const [rows, setRows] = useState([]);
  const [date, setDate] = useState(todayIST());
  const [entries, setEntries] = useState([{ rid: crypto.randomUUID(), item_id: "", qty: "", notes: "" }]);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    api.get("/items").then(({ data }) => setItems(data));
    api.get("/stock").then(({ data }) => {
      setStockMap(Object.fromEntries(data.map((s) => [s.item_id, s.qty_left])));
    });
    api.get("/usage").then(({ data }) => setRows(data));
  }, []);

  useEffect(() => { load(); }, [load]);

  const removeRow = (rid) => setEntries((e) => e.filter((r) => r.rid !== rid));
  const updateRow = (rid, key, val) =>
    setEntries((e) => e.map((r) => (r.rid === rid ? { ...r, [key]: val } : r)));

  const submit = async (e) => {
    e.preventDefault();
    const valid = entries.filter((r) => r.item_id && parseFloat(r.qty) > 0);
    if (valid.length === 0) return toast.error("Add at least one valid item & quantity");
    // warn for overuse
    for (const r of valid) {
      const left = stockMap[r.item_id] ?? 0;
      if (parseFloat(r.qty) > left) {
        const item = items.find((i) => i.id === r.item_id);
        if (!window.confirm(`Usage of ${r.qty} ${item?.unit} for "${item?.name}" exceeds available stock (${left}). Continue anyway?`)) {
          return;
        }
        break;
      }
    }
    setSaving(true);
    try {
      for (const r of valid) {
        await api.post("/usage", {
          item_id: r.item_id, date, quantity_used: parseFloat(r.qty), notes: r.notes || "",
        });
      }
      toast.success(`${valid.length} usage entr${valid.length === 1 ? "y" : "ies"} saved`);
      setEntries([{ rid: crypto.randomUUID(), item_id: "", qty: "", notes: "" }]);
      load();
      api.get("/stock").then(({ data }) => setStockMap(Object.fromEntries(data.map((s) => [s.item_id, s.qty_left]))));
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  };

  const voidRow = async (id) => {
    const reason = window.prompt("Reason for voiding this entry (required):");
    if (!reason?.trim()) return;
    try {
      await api.patch(`/usage/${id}/void`, { reason: reason.trim() });
      toast.success("Entry voided");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const activeItems = items.filter((i) => i.is_active);

  return (
    <div className="space-y-6 animate-fade-up" data-testid="usage-page">
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Kitchen</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Daily Usage</h1>
        <p className="text-slate-600 text-sm mt-1">Record items consumed in the kitchen today</p>
      </div>

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <form onSubmit={submit} className="space-y-4">
            <div className="flex gap-3">
              <div>
                <Label className="text-sm mb-1.5 block">Date</Label>
                <Input type="date" data-testid="usage-date-input" value={date} onChange={(e) => setDate(e.target.value)} className="h-11 bg-white" />
              </div>
            </div>

            <div className="space-y-2" data-testid="usage-entries">
              {entries.map((r, i) => {
                const it = items.find((x) => x.id === r.item_id);
                const left = it ? stockMap[r.item_id] ?? 0 : null;
                const exceeds = it && parseFloat(r.qty || 0) > (stockMap[r.item_id] ?? 0);
                return (
                  <div key={r.rid} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end p-3 rounded-xl bg-orange-50/40 border border-orange-100">
                    <div className="md:col-span-4">
                      <Label className="text-xs mb-1 block">Item</Label>
                      <Select value={r.item_id} onValueChange={(v) => updateRow(r.rid, "item_id", v)}>
                        <SelectTrigger data-testid={`usage-item-${i}`} className="h-11 bg-white"><SelectValue placeholder="Select item" /></SelectTrigger>
                        <SelectContent>
                          {activeItems.map((it) => <SelectItem key={it.id} value={it.id}>{it.name}</SelectItem>)}
                        </SelectContent>
                      </Select>
                      {it && <div className="text-[11px] text-slate-500 mt-1">Available: <b className={exceeds ? "text-red-600" : ""}>{left} {it.unit}</b></div>}
                    </div>
                    <div className="md:col-span-2">
                      <Label className="text-xs mb-1 block">Qty {it && `(${it.unit})`}</Label>
                      <Input type="number" step="0.01" min="0" data-testid={`usage-qty-${i}`}
                        value={r.qty} onChange={(e) => updateRow(r.rid, "qty", e.target.value)} className="h-11 bg-white tabular-nums" />
                    </div>
                    <div className="md:col-span-5">
                      <Label className="text-xs mb-1 block">Notes (optional)</Label>
                      <Input data-testid={`usage-notes-${i}`} value={r.notes} onChange={(e) => updateRow(r.rid, "notes", e.target.value)} className="h-11 bg-white" />
                    </div>
                    <div className="md:col-span-1 flex justify-end">
                      {entries.length > 1 && (
                        <Button type="button" variant="ghost" onClick={() => removeRow(r.rid)} className="h-11 w-11 p-0 text-red-600 hover:bg-red-50" data-testid={`usage-remove-${i}`}>
                          <X size={18} />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              <Button type="button" variant="outline" onClick={addRow} data-testid="usage-add-row"
                className="rounded-full border-orange-200 text-orange-700 hover:bg-orange-50">
                <Plus size={16} className="mr-1" />Add Another Item
              </Button>
              <Button type="submit" disabled={saving} data-testid="usage-submit"
                className="rounded-full bg-orange-600 hover:bg-orange-700 px-6 active:scale-95 sm:ml-auto">
                {saving ? "Saving..." : "Save All Entries"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <h3 className="font-display text-lg font-semibold text-slate-900 mb-3">Recent Usage</h3>
          {rows.length === 0 ? (
            <div className="text-center py-10 text-slate-500">
              <ChefHat className="mx-auto text-orange-300 mb-2" size={36} />
              <p>No usage records yet.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Item</TableHead>
                    <TableHead className="text-right">Qty Used</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead>By</TableHead>
                    <TableHead>Logged at</TableHead>
                    {canAdd && <TableHead></TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id} data-testid={`usage-row-${r.id}`}>
                      <TableCell className="tabular-nums">{fmtDate(r.date)}</TableCell>
                      <TableCell className="font-medium">{r.item_name}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.quantity_used} {r.unit}</TableCell>
                      <TableCell className="text-slate-500 text-sm">{r.notes || "—"}</TableCell>
                      <TableCell className="text-xs text-slate-500">{r.created_by_name}</TableCell>
                      <TableCell className="text-xs text-slate-400 tabular-nums whitespace-nowrap">{fmtTimestamp(r.created_at)}</TableCell>
                      {canAdd && (
                        <TableCell>
                          <button title="Void this entry" onClick={() => voidRow(r.id)}
                            className="text-red-400 hover:text-red-600 transition-colors" data-testid={`void-usage-${r.id}`}>
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
