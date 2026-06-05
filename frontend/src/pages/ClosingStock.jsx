/**
 * ClosingStock — End-of-day physical shelf count page.
 *
 * Design:
 *   - No business logic here — all in useClosingStock hook
 *   - No API calls here — all through the hook
 *   - Follows existing page patterns (useSave, role checks, etc.)
 *
 * Flow:
 *   1. Lokesh selects date (default today)
 *   2. Selects item from dropdown
 *   3. Enters physical qty on shelf
 *   4. App computes: consumed = opening + purchased - closing
 *   5. App shows variance vs manual usage
 *   6. High variance items flagged with WastageAlert
 */

import { useEffect, useState, useMemo } from "react";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";
import { useClosingStock } from "@/hooks/useClosingStock";
import { WastageAlert } from "@/components/WastageAlert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Package, ClipboardList, AlertTriangle } from "lucide-react";
import { todayIST, fmtDate, fmtTimestamp } from "@/lib/format";

export default function ClosingStock() {
  const { user } = useAuth();
  const canRecord = ["admin", "staff"].includes(user?.role);

  // Form state
  const [date, setDate]     = useState(todayIST());
  const [itemId, setItemId] = useState("");
  const [closingQty, setClosingQty] = useState("");
  const [notes, setNotes]   = useState("");
  const [items, setItems]   = useState([]);

  // Hook — all API logic
  const { saving, loading, entries, summary, recordCount, loadByDate, loadSummary } =
    useClosingStock();

  // Load items on mount
  useEffect(() => {
    api.get("/items")
      .then(({ data }) => setItems(data.filter((i) => i.is_active)))
      .catch((err) => console.error("Failed to load items:", err));
  }, []);

  // Load entries + summary when date changes
  useEffect(() => {
    if (date) {
      loadByDate(date);
      loadSummary(date);
    }
  }, [date, loadByDate, loadSummary]);

  const selectedItem = useMemo(
    () => items.find((i) => i.id === itemId),
    [items, itemId]
  );

  // Already counted items for today (disable re-entry or show current value)
  const countedMap = useMemo(
    () => Object.fromEntries(entries.map((e) => [e.item_id, e])),
    [entries]
  );

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!itemId || closingQty === "") return;

    const result = await recordCount({
      date,
      item_id: itemId,
      closing_qty: parseFloat(closingQty),
      notes,
    });

    if (result) {
      // Refresh
      setItemId("");
      setClosingQty("");
      setNotes("");
      loadByDate(date);
      loadSummary(date);
    }
  };

  return (
    <div className="space-y-6 animate-fade-up" data-testid="closing-stock-page">

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">
            Closing Stock
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            End-of-day physical shelf count — app computes actual consumption &amp; wastage
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Label className="text-sm text-slate-600">Date</Label>
          <Input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            max={todayIST()}
            className="w-44 h-10 bg-white"
          />
        </div>
      </div>

      {/* Wastage Alerts */}
      {summary && (
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <AlertTriangle size={16} className="text-orange-500" />
              Wastage Summary — {fmtDate(date)}
              <Badge variant="outline" className="ml-auto text-xs">
                {summary.items_counted}/{summary.total_items} items counted
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <WastageAlert
              items={summary.high_variance_items}
              wastage_cost_est={summary.wastage_cost_est}
            />
          </CardContent>
        </Card>
      )}

      {/* Entry Form */}
      {canRecord && (
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Package size={16} className="text-orange-500" />
              Record Physical Count
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit}
              className="grid grid-cols-1 md:grid-cols-12 gap-3 items-start">

              {/* Item */}
              <div className="md:col-span-4">
                <Label className="text-sm mb-1.5 block">Item</Label>
                <Select value={itemId} onValueChange={setItemId}>
                  <SelectTrigger className="h-11 bg-white">
                    <SelectValue placeholder="Select item" />
                  </SelectTrigger>
                  <SelectContent>
                    {items.map((it) => (
                      <SelectItem key={it.id} value={it.id}>
                        {it.name}
                        {countedMap[it.id] && (
                          <span className="ml-2 text-green-600 text-xs">✓ counted</span>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="text-xs text-slate-500 mt-1 h-4">
                  {selectedItem
                    ? `${selectedItem.category} · unit: ${selectedItem.unit}`
                    : ""}
                </div>
              </div>

              {/* Closing Qty */}
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">
                  Shelf Count {selectedItem && `(${selectedItem.unit})`}
                </Label>
                <Input
                  type="number" step="0.01" min="0"
                  value={closingQty}
                  onChange={(e) => setClosingQty(e.target.value)}
                  placeholder="0"
                  className="h-11 bg-white tabular-nums"
                />
                <div className="h-4" />
              </div>

              {/* Notes */}
              <div className="md:col-span-4">
                <Label className="text-sm mb-1.5 block">Notes (optional)</Label>
                <Input
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. found spillage, moved to fridge..."
                  className="h-11 bg-white"
                />
                <div className="h-4" />
              </div>

              {/* Save */}
              <div className="md:col-span-2 flex items-start pt-6">
                <Button
                  type="submit"
                  disabled={saving || !itemId || closingQty === ""}
                  className="w-full h-11 rounded-full bg-orange-600 hover:bg-orange-700">
                  {saving ? "Saving..." : "Save Count"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Today's Entries */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <ClipboardList size={16} className="text-orange-500" />
            Counts Recorded — {fmtDate(date)}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-4 space-y-2">
              {[1, 2, 3].map((k) => <Skeleton key={k} className="h-12 rounded-xl" />)}
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <Package size={32} className="mx-auto mb-2 opacity-40" />
              <p className="text-sm">No counts recorded for {fmtDate(date)}</p>
              {canRecord && (
                <p className="text-xs mt-1">
                  Select an item above and enter shelf quantity
                </p>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-xs text-slate-500 uppercase tracking-wide">
                    <th className="text-left px-4 py-3">Item</th>
                    <th className="text-right px-4 py-3">Opening</th>
                    <th className="text-right px-4 py-3">Purchased</th>
                    <th className="text-right px-4 py-3">Closing</th>
                    <th className="text-right px-4 py-3">Consumed</th>
                    <th className="text-right px-4 py-3">Manual Usage</th>
                    <th className="text-right px-4 py-3">Variance</th>
                    <th className="text-left px-4 py-3">Logged at</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e, i) => (
                    <tr key={e.id}
                      className={`border-b border-slate-50 hover:bg-slate-50/60 transition-colors
                        ${e.wastage_flag ? "bg-red-50/30" : ""}`}>
                      <td className="px-4 py-3 font-medium">
                        {e.item_name}
                        <span className="text-xs text-slate-400 ml-1">({e.unit})</span>
                        {e.wastage_flag && (
                          <Badge className="ml-2 text-xs bg-red-100 text-red-700 border-0">
                            ⚠️ {e.variance_pct}% variance
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                        {e.opening_qty}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-blue-600">
                        +{e.purchased_today}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums font-medium">
                        {e.closing_qty}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums font-semibold text-slate-800">
                        {e.consumed}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-slate-500">
                        {e.manual_usage}
                      </td>
                      <td className={`px-4 py-3 text-right tabular-nums font-medium
                        ${e.variance > 0 ? "text-red-600" : e.variance < 0 ? "text-green-600" : "text-slate-400"}`}>
                        {e.variance > 0 ? "+" : ""}{e.variance}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">
                        {fmtTimestamp(e.recorded_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
