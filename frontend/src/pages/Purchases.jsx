import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { Plus, Receipt, Search, Ban, ChevronDown } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { inr, fmtDate, fmtTimestamp, todayIST } from "@/lib/format";
import { cn } from "@/lib/utils";
import VoidDialog from "@/components/VoidDialog";
import { ItemDialog } from "@/pages/Items";

/** Item combobox with search + "add new" affordance for the on-the-fly flow. */
function ItemPicker({ items, value, onChange, onCreateNew }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const selected = items.find((i) => i.id === value);
  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return items;
    return items.filter((i) => i.name.toLowerCase().includes(query) || (i.category || "").toLowerCase().includes(query));
  }, [q, items]);

  return (
    <div ref={ref} className="relative" data-testid="item-picker">
      <button type="button" onClick={() => setOpen((o) => !o)}
        className={cn(
          "w-full h-11 px-3 rounded-md border bg-white text-left text-sm flex items-center justify-between gap-2 focus:outline-none focus:ring-2 focus:ring-orange-500",
          selected ? "text-slate-900" : "text-slate-400"
        )}
        data-testid="item-picker-trigger">
        <span className="truncate">
          {selected ? (
            <>
              {selected.name}
              <span className="text-slate-400 text-xs ml-1">({selected.base_unit})</span>
            </>
          ) : "Select item"}
        </span>
        <ChevronDown size={16} className="text-slate-400 shrink-0" />
      </button>

      {open && (
        <div className="absolute z-30 top-full left-0 right-0 mt-1 rounded-lg border bg-white shadow-lg">
          <div className="relative p-2 border-b">
            <Search className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
            <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search items..." data-testid="item-picker-search"
              className="w-full h-9 pl-8 pr-2 rounded-md border text-sm focus:outline-none focus:ring-1 focus:ring-orange-500" />
          </div>
          <div className="max-h-64 overflow-y-auto">
            {filtered.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-slate-500">No items match.</div>
            )}
            {filtered.map((i) => (
              <button type="button" key={i.id}
                onClick={() => { onChange(i.id); setOpen(false); setQ(""); }}
                data-testid={`item-picker-option-${i.id}`}
                className="w-full px-3 py-2.5 text-left text-sm hover:bg-orange-50 flex items-center justify-between">
                <div className="min-w-0">
                  <div className="font-medium text-slate-900 truncate">{i.name}</div>
                  <div className="text-[11px] text-slate-500 truncate">{i.category || "."}. {i.base_unit}</div>
                </div>
              </button>
            ))}
          </div>
          <button type="button" onClick={() => { setOpen(false); onCreateNew(q); }}
            data-testid="item-picker-add-new"
            className="w-full px-3 py-2.5 border-t bg-orange-50 hover:bg-orange-100 text-orange-800 text-sm font-medium flex items-center gap-1">
            <Plus size={14} /> Add new item{q ? ` "${q}"` : ""}
          </button>
        </div>
      )}
    </div>
  );
}

export default function Purchases() {
  const { user } = useAuth();
  const canAdd = ["admin", "staff"].includes(user.role);

  const [items, setItems] = useState([]);
  const [rows, setRows] = useState(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const [itemId, setItemId] = useState("");
  const [date, setDate] = useState(todayIST());
  const [qty, setQty] = useState("");
  const [unit, setUnit] = useState("");
  const [price, setPrice] = useState("");
  const [saving, setSaving] = useState(false);
  const [voidId, setVoidId] = useState(null);
  const [dlgOpen, setDlgOpen] = useState(false);
  const [dlgInitial, setDlgInitial] = useState(null);

  const loadItems = useCallback(async () => {
    try { const { data } = await api.get("/items"); setItems(data); }
    catch {}
  }, []);

  const loadRows = useCallback(async () => {
    try {
      const params = { ...(start ? { start } : {}), ...(end ? { end } : {}) };
      const { data } = await api.get("/purchases", { params });
      setRows(data);
    } catch {}
  }, [start, end]);

  useEffect(() => { loadItems(); }, [loadItems]);
  useEffect(() => { loadRows(); }, [loadRows]);

  const selectedItem = items.find((i) => i.id === itemId);

  // When item changes, prefill unit + price from item defaults.
  useEffect(() => {
    if (!selectedItem) return;
    const defaultUnit = (selectedItem.units || []).find((u) => u.is_default) || (selectedItem.units || [])[0];
    setUnit((prev) => defaultUnit ? defaultUnit.name : prev);
    setPrice((prev) => prev || (selectedItem.default_price ? String(selectedItem.default_price) : ""));
  }, [selectedItem]);

  const chosenUnit = useMemo(() => {
    if (!selectedItem) return null;
    return (selectedItem.units || []).find((u) => u.name === unit);
  }, [selectedItem, unit]);

  const total = (parseFloat(qty || 0) * parseFloat(price || 0)) || 0;
  const baseQuantity = chosenUnit ? (parseFloat(qty || 0) * parseFloat(chosenUnit.conversion_factor)) : 0;

  const runningTotal = (rows || []).reduce((a, b) => a + (b.total_cost || 0), 0);

  const dayTotal   = (rows || []).filter((r) => r.date === todayIST()).reduce((a, b) => a + b.total_cost, 0);

  const validateAndSave = async (e) => {
    e.preventDefault();
    if (!itemId) return toast.error("Select an item");
    if (!(parseFloat(qty) > 0)) return toast.error("Quantity must be greater than 0");
    if (!chosenUnit) return toast.error("Select a valid unit");
    if (!(parseFloat(price) > 0)) return toast.error("Price must be greater than 0");
    setSaving(true);
    try {
      await api.post("/purchases", {
        item_id: itemId,
        date,
        quantity: parseFloat(qty),
        unit: chosenUnit.name,
        unit_conversion_factor: parseFloat(chosenUnit.conversion_factor),
        price_per_unit: parseFloat(price),
      });
      toast.success("Purchase saved");
      setQty(""); setPrice(selectedItem?.default_price ? String(selectedItem.default_price) : "");
      loadRows();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const openAddDialog = (prefName) => {
    setDlgInitial(prefName ? { name: prefName, base_unit: "", default_price: 0, units: [] } : null);
    setDlgOpen(true);
  };

  const onItemDialogSaved = (saved) => {
    setItems((prev) => {
      const others = prev.filter((p) => p.id !== saved.id);
      return [...others, saved].sort((a, b) => a.name.localeCompare(b.name));
    });
    setItemId(saved.id);
  };

  const handleVoidConfirm = async (reason) => {
    const id = voidId; setVoidId(null);
    try { await api.patch(`/purchases/${id}/void`, { reason }); toast.success("Purchase voided"); loadRows(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  return (
    <div className="space-y-5 animate-fade-up" data-testid="purchases-page">
      <VoidDialog open={!!voidId} onConfirm={handleVoidConfirm}
        onCancel={() => setVoidId(null)} entryLabel="purchase" />

      <ItemDialog open={dlgOpen} onOpenChange={setDlgOpen} initial={dlgInitial}
        onSaved={onItemDialogSaved} />

      {/* Header + sticky totals */}
      <div>
        <div className="flex items-end justify-between gap-3 flex-wrap">
          <div>
            <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Inbound</div>
            <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Purchases</h1>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 mt-3" data-testid="purchases-totals">
          <Card className="rounded-2xl border-orange-900/10 shadow-sm">
            <CardContent className="p-3 md:p-4">
              <div className="text-[11px] uppercase tracking-wider text-slate-500">Today</div>
              <div className="font-display font-bold text-xl md:text-2xl tabular-nums text-slate-900"
                data-testid="purchases-today-total">{inr(dayTotal)}</div>
            </CardContent>
          </Card>
          <Card className="rounded-2xl border-orange-900/10 shadow-sm">
            <CardContent className="p-3 md:p-4">
              <div className="text-[11px] uppercase tracking-wider text-slate-500">Filtered range</div>
              <div className="font-display font-bold text-xl md:text-2xl tabular-nums text-orange-700"
                data-testid="purchases-range-total">{inr(runningTotal)}</div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Add form */}
      {canAdd && (
        <Card className="rounded-2xl border-orange-900/10 shadow-sm">
          <CardContent className="p-4 md:p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-3 flex items-center gap-2">
              <Plus size={18} className="text-orange-600" />Add purchase
            </h3>
            <form onSubmit={validateAndSave} className="space-y-3">
              <div>
                <Label className="text-sm mb-1.5 block">Item</Label>
                <ItemPicker items={items.filter((i) => i.is_active)}
                  value={itemId} onChange={setItemId}
                  onCreateNew={openAddDialog} />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-sm mb-1.5 block">Date</Label>
                  <Input type="date" value={date} max={todayIST()}
                    onChange={(e) => setDate(e.target.value)} className="h-11 bg-white"
                    data-testid="purchase-date-input" />
                </div>
                <div>
                  <Label className="text-sm mb-1.5 block">Unit</Label>
                  <Select value={unit} onValueChange={setUnit}
                    disabled={!selectedItem}>
                    <SelectTrigger className="h-11 bg-white" data-testid="purchase-unit-select">
                      <SelectValue placeholder="Select item first" />
                    </SelectTrigger>
                    <SelectContent>
                      {(selectedItem?.units || []).map((u) => (
                        <SelectItem key={u.name} value={u.name}>
                          {u.name} (×{u.conversion_factor} {selectedItem.base_unit})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-sm mb-1.5 block">Quantity{unit ? ` (${unit})` : ""}</Label>
                  <Input type="number" step="0.01" min="0" inputMode="decimal"
                    value={qty} onChange={(e) => setQty(e.target.value)}
                    placeholder="0" className="h-11 bg-white tabular-nums text-lg"
                    data-testid="purchase-qty-input" />
                </div>
                <div>
                  <Label className="text-sm mb-1.5 block">Price / {unit || "unit"} (₹)</Label>
                  <Input type="number" step="0.01" min="0" inputMode="decimal"
                    value={price} onChange={(e) => setPrice(e.target.value)}
                    placeholder="0.00" className="h-11 bg-white tabular-nums text-lg"
                    data-testid="purchase-price-input" />
                </div>
              </div>

              <div className="flex items-center justify-between gap-3 flex-wrap p-3 rounded-xl bg-orange-50 border border-orange-100"
                data-testid="purchase-total-preview">
                <div className="text-sm text-slate-600">
                  Total
                  {chosenUnit && qty && (
                    <span className="text-[11px] text-slate-500 ml-2">
                      ({baseQuantity} {selectedItem?.base_unit} in base)
                    </span>
                  )}
                </div>
                <div className="font-display font-bold text-2xl text-orange-700 tabular-nums">
                  {inr(total)}
                </div>
              </div>

              <Button type="submit" disabled={saving}
                data-testid="purchase-submit-button"
                className="w-full h-12 rounded-full bg-orange-600 hover:bg-orange-700 text-base font-medium active:scale-[0.98]">
                {saving ? "Saving..." : "Save purchase"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* History */}
      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-4 md:p-5">
          <div className="flex flex-col md:flex-row md:items-end gap-3 mb-4">
            <div className="flex-1">
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">History</Label>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">From</Label>
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)}
                className="h-10 bg-white" data-testid="purchases-filter-start" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">To</Label>
              <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
                className="h-10 bg-white" data-testid="purchases-filter-end" />
            </div>
          </div>

          {rows === null ? (
            <div className="py-8 text-center text-sm text-slate-400">Loading...</div>
          ) : rows.length === 0 ? (
            <div className="text-center py-10 text-slate-500" data-testid="purchases-empty-state">
              <Receipt className="mx-auto text-orange-300 mb-2" size={36} />
              <p className="font-medium">No purchases yet</p>
              <p className="text-sm mt-1">Tap Save purchase above to record the first one.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Item</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead className="text-right">Price</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead>By</TableHead>
                    {canAdd && <TableHead></TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id} data-testid={`purchase-row-${r.id}`}>
                      <TableCell className="tabular-nums">{fmtDate(r.date)}</TableCell>
                      <TableCell className="font-medium">{r.item_name}</TableCell>
                      <TableCell className="text-right tabular-nums whitespace-nowrap">
                        {r.quantity} {r.unit}
                        {r.unit && r.base_unit && r.unit !== r.base_unit && (
                          <span className="text-[10px] text-slate-400 ml-1">= {r.base_quantity} {r.base_unit}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{inr(r.price_per_unit)}</TableCell>
                      <TableCell className="text-right tabular-nums font-semibold">{inr(r.total_cost)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{r.created_by_name}</TableCell>
                      {canAdd && (
                        <TableCell>
                          <button title="Void" onClick={() => setVoidId(r.id)}
                            className="text-red-400 hover:text-red-600 transition-colors"
                            data-testid={`void-purchase-${r.id}`}>
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
