import { useEffect, useMemo, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { inr, fmtDate, fmtTimestamp, todayIST } from "@/lib/format";
import { Plus, Receipt, Ban, Download } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { SKELETON_KEYS } from "@/lib/skeletons";
import { useSave } from "@/hooks/useSave";
import { useDateFilter } from "@/hooks/useDateFilter";
import DuplicateWarningDialog from "@/components/DuplicateWarningDialog";
import VoidDialog from "@/components/VoidDialog";

export default function Purchases() {
  const [params] = useSearchParams();
  const { user } = useAuth();
  const canAdd = ["admin", "staff"].includes(user.role);
  const [items, setItems] = useState([]);
  const [rows, setRows] = useState(null);
  const [filterItem, setFilterItem] = useState("all");
  const { start, end, setStart, setEnd, dateParams } = useDateFilter();
  const [voidingId, setVoidingId] = useState(null);
  const [voidDialogId, setVoidDialogId] = useState(null);

  const [itemId, setItemId] = useState(params.get("item") || "");
  const [date, setDate] = useState(todayIST());
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [errors, setErrors] = useState({});

  useEffect(() => { api.get("/items").then(({ data }) => setItems(data)).catch((err) => console.error(err)); }, []);
  const load = useCallback(() => {
    const q = { ...dateParams, ...(filterItem !== "all" ? { item_id: filterItem } : {}) };
    api.get("/purchases", { params: q }).then(({ data }) => setRows(data)).catch((err) => console.error(err));
  }, [filterItem, dateParams]);
  useEffect(() => { load(); }, [load]);

  const selectedItem = items.find((i) => i.id === itemId);
  const total = (parseFloat(qty || 0) * parseFloat(price || 0)) || 0;
  const runningTotal = (rows || []).reduce((a, b) => a + (b.total_cost || 0), 0);

  const { save, saving, dupDialog, confirmDuplicate, cancelDuplicate } = useSave(
    () => api.post("/purchases", {
      item_id: itemId, date, quantity: parseFloat(qty), price_per_unit: parseFloat(price),
    }),
    { successMessage: "Purchase saved", onSuccess: () => { setQty(""); setPrice(""); setErrors({}); load(); } }
  );

  const submit = (e) => {
    e.preventDefault();
    const next = {};
    if (!itemId) next.item = "Please select an item";
    if (!(parseFloat(qty) > 0)) next.qty = "Quantity must be greater than 0";
    if (!price || !(parseFloat(price) > 0)) next.price = "Price must be greater than ₹0";
    setErrors(next);
    if (Object.keys(next).length) {
      toast.error(Object.values(next)[0]);
      return;
    }
    save();
  };

  const voidRow = (id) => setVoidDialogId(id);

  const handleVoidConfirm = async (reason) => {
    const id = voidDialogId;
    setVoidDialogId(null);
    try {
      await api.patch(`/purchases/${id}/void`, { reason });
      toast.success("Entry voided");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const activeItems = items.filter((i) => i.is_active);

  return (
    <div className="space-y-6 animate-fade-up" data-testid="purchases-page">
      <DuplicateWarningDialog
        open={dupDialog}
        onConfirm={confirmDuplicate}
        onCancel={cancelDuplicate}
        message="A purchase for the same item and quantity was just recorded seconds ago. Did you intend to enter this again?"
      />
      <VoidDialog
        open={!!voidDialogId}
        onConfirm={handleVoidConfirm}
        onCancel={() => setVoidDialogId(null)}
        entryLabel="purchase"
      />
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Inventory</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Purchases</h1>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <Button onClick={async () => {
            try {
              const { data, headers } = await api.get("/export/purchases.csv", { params: dateParams, responseType: "blob" });
              const url = window.URL.createObjectURL(new Blob([data], { type: "text/csv" }));
              const a = document.createElement("a");
              a.href = url;
              const cd = headers["content-disposition"] || "";
              const m = cd.match(/filename="?([^"]+)"?/);
              a.download = m ? m[1] : "purchases.csv";
              document.body.appendChild(a); a.click(); a.remove();
              window.URL.revokeObjectURL(url);
            } catch { toast.error("Failed to export CSV"); }
          }} variant="outline" data-testid="purchases-export-csv-button" className="rounded-full border-orange-300 text-orange-700">
            <Download size={16} className="mr-1" />Export CSV
          </Button>
          <div className="bg-white rounded-2xl border border-orange-900/10 px-5 py-3 shadow-sm">
            <div className="text-xs text-slate-500 uppercase tracking-wider">Running total (filtered)</div>
            <div className="font-display font-bold text-xl text-orange-700 tabular-nums" data-testid="purchases-running-total">{inr(runningTotal)}</div>
          </div>
        </div>
      </div>

      {canAdd && (
        <Card className="rounded-2xl border-orange-900/10 shadow-sm">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Plus size={18} className="text-orange-600" />Add Purchase
            </h3>
            <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-12 gap-3 items-start">
              <div className="md:col-span-4">
                <Label className="text-sm mb-1.5 block">Item</Label>
                <Select value={itemId} onValueChange={setItemId}>
                  <SelectTrigger data-testid="purchase-item-select" className="h-11 bg-white"><SelectValue placeholder="Select item" /></SelectTrigger>
                  <SelectContent>
                    {activeItems.map((it) => (
                      <SelectItem key={it.id} value={it.id}>{it.name} <span className="text-slate-400 text-xs ml-1">({it.unit})</span></SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="text-xs text-slate-500 mt-1 h-4">
                  {selectedItem ? `${selectedItem.category} · per ${selectedItem.unit}` : ""}
                </div>
              </div>
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">Date</Label>
                <Input type="date" data-testid="purchase-date-input" value={date} onChange={(e) => setDate(e.target.value)} className="h-11 bg-white" />
                <div className="h-4" />
              </div>
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">Quantity {selectedItem && `(${selectedItem.unit})`}</Label>
                <Input type="number" step="0.01" min="0" data-testid="purchase-qty-input" value={qty}
                  onChange={(e) => { setQty(e.target.value); if (errors.qty) setErrors(p => ({...p, qty: undefined})); }}
                  placeholder="0"
                  className={cn("h-11 bg-white tabular-nums", errors.qty && "border-red-500 focus-visible:ring-red-500")} />
                <div className="h-4 text-[11px] text-red-600 mt-0.5" data-testid="purchase-qty-error">{errors.qty || ""}</div>
              </div>
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">Price (₹ per unit)</Label>
                <Input type="number" step="0.01" min="0.01" data-testid="purchase-price-input" value={price}
                  onChange={(e) => { setPrice(e.target.value); if (errors.price) setErrors(p => ({...p, price: undefined})); }}
                  placeholder="0.00"
                  className={cn("h-11 bg-white tabular-nums", errors.price && "border-red-500 focus-visible:ring-red-500")} />
                <div className="h-4 text-[11px] text-red-600 mt-0.5" data-testid="purchase-price-error">{errors.price || ""}</div>
              </div>
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">Total</Label>
                <div className="h-11 px-3 rounded-lg bg-orange-50 border border-orange-200 flex items-center font-semibold text-orange-700 tabular-nums" data-testid="purchase-total-preview">{inr(total)}</div>
                <div className="h-4" />
              </div>
              <div className="md:col-span-12">
                <Button type="submit" disabled={saving} data-testid="purchase-submit-button"
                  className="rounded-full bg-orange-600 hover:bg-orange-700 px-6 active:scale-95">
                  {saving ? "Saving..." : "Save Purchase"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <div className="flex flex-col md:flex-row md:items-end gap-3 mb-4">
            <div className="flex-1">
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">Filter Item</Label>
              <Select value={filterItem} onValueChange={setFilterItem}>
                <SelectTrigger data-testid="filter-item" className="h-10 bg-white"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Items</SelectItem>
                  {items.map((it) => <SelectItem key={it.id} value={it.id}>{it.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">From</Label>
              <Input type="date" data-testid="filter-start" value={start} onChange={(e) => setStart(e.target.value)} className="h-10 bg-white" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">To</Label>
              <Input type="date" data-testid="filter-end" value={end} onChange={(e) => setEnd(e.target.value)} className="h-10 bg-white" />
            </div>
          </div>

          {rows === null ? (
            <div className="space-y-2">{SKELETON_KEYS.slice(0, 5).map((k) => <Skeleton key={k} className="h-10 rounded-lg" />)}</div>
          ) : rows.length === 0 ? (
            <div className="text-center py-10 text-slate-500" data-testid="purchases-empty-state">
              <Receipt className="mx-auto text-orange-300 mb-2" size={36} />
              <p className="font-medium">No purchase records yet</p>
              <p className="text-sm mt-1">Record your first purchase above — stock and P&L update live.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Item</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead className="text-right">Price</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead>By</TableHead>
                    <TableHead>Logged at</TableHead>
                    {canAdd && <TableHead></TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id} data-testid={`purchase-row-${r.id}`}>
                      <TableCell className="tabular-nums">{fmtDate(r.date)}</TableCell>
                      <TableCell className="font-medium">{r.item_name}</TableCell>
                      <TableCell className="text-slate-500">{r.category}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.quantity} {r.unit}</TableCell>
                      <TableCell className="text-right tabular-nums">{inr(r.price_per_unit)}</TableCell>
                      <TableCell className="text-right tabular-nums font-semibold">{inr(r.total_cost)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{r.created_by_name}</TableCell>
                      <TableCell className="text-xs text-slate-400 tabular-nums whitespace-nowrap">{fmtTimestamp(r.created_at)}</TableCell>
                      {canAdd && (
                        <TableCell>
                          <button title="Void this entry" onClick={() => voidRow(r.id)}
                            className="text-red-400 hover:text-red-600 transition-colors" data-testid={`void-purchase-${r.id}`}>
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
