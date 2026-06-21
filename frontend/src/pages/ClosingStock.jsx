/**
 * ClosingStock — End-of-day physical shelf count page.
 *
 * Flow:
 *   1. Lokesh selects date (default today)
 *   2. Selects item, enters physical qty on shelf
 *   3. App computes: consumed = opening + purchased - closing
 *   4. Table shows clean summary — no wastage until recipe mapping is built
 *
 * Wastage analysis is intentionally excluded until Menu Management
 * and Recipe Mapping are implemented. At that point:
 *   wastage = consumed - (dishes_sold × ingredient_qty_per_dish)
 */

import { useEffect, useState, useMemo } from "react";
import logger from "@/lib/logger";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";
import { useClosingStock } from "@/hooks/useClosingStock";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Package, ClipboardList, CheckCircle2 } from "lucide-react";
import { todayIST, fmtDate, fmtTimestamp } from "@/lib/format";

export default function ClosingStock() {
  const { user } = useAuth();
  const canRecord = ["admin", "staff"].includes(user?.role);

  // Form state
  const [date, setDate]         = useState(todayIST());
  const [itemId, setItemId]     = useState("");
  const [closingQty, setClosingQty] = useState("");
  const [notes, setNotes]       = useState("");
  const [items, setItems]       = useState([]);

  // Hook — all API logic lives here
  const { saving, loading, entries, recordCount, loadByDate } = useClosingStock();

  // Load active items on mount
  useEffect(() => {
    api.get("/items")
      .then(({ data }) => setItems(data.filter((i) => i.is_active)))
      .catch((err) => logger.error("Failed to load items:", err));
  }, []);

  // Reload entries when date changes
  useEffect(() => {
    if (date) loadByDate(date);
  }, [date, loadByDate]);

  const selectedItem = useMemo(
    () => items.find((i) => i.id === itemId),
    [items, itemId]
  );

  // Map item_id → entry so we can show "✓ counted" in dropdown
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
      setItemId("");
      setClosingQty("");
      setNotes("");
      loadByDate(date);
    }
  };

  const uncountedItems = items.filter((i) => !countedMap[i.id]);
  const countedCount   = entries.length;
  const totalCount     = items.length;

  return (
    <div className="space-y-6 animate-fade-up" data-testid="closing-stock-page">

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">
            Kitchen
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">
            Closing Stock
          </h1>
          <p className="text-slate-600 text-sm mt-1">
            Count what's left on the shelf — app calculates what was consumed today
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

      {/* Progress bar — how many items counted today */}
      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700">
              Items counted today
            </span>
            <Badge
              variant="outline"
              className={`text-xs ${
                countedCount === totalCount && totalCount > 0
                  ? "border-green-400 text-green-700 bg-green-50"
                  : "border-orange-300 text-orange-700 bg-orange-50"
              }`}
            >
              {countedCount} / {totalCount}
            </Badge>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2">
            <div
              className="bg-orange-500 h-2 rounded-full transition-all duration-500"
              style={{ width: totalCount > 0 ? `${(countedCount / totalCount) * 100}%` : "0%" }}
            />
          </div>
          {countedCount === totalCount && totalCount > 0 && (
            <div className="flex items-center gap-1.5 mt-2 text-green-700 text-xs font-medium">
              <CheckCircle2 size={13} />
              All items counted for {fmtDate(date)}
            </div>
          )}
          {uncountedItems.length > 0 && (
            <p className="text-xs text-slate-500 mt-2">
              Still needed: {uncountedItems.slice(0, 4).map((i) => i.name).join(", ")}
              {uncountedItems.length > 4 && ` +${uncountedItems.length - 4} more`}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Entry Form */}
      {canRecord && (
        <Card className="rounded-2xl border-orange-900/10 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Package size={16} className="text-orange-500" />
              Record Physical Count
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={handleSubmit}
              className="grid grid-cols-1 md:grid-cols-12 gap-3 items-start"
            >
              {/* Item */}
              <div className="md:col-span-4">
                <Label className="text-sm mb-1.5 block">Item</Label>
                <Select value={itemId} onValueChange={setItemId}>
                  <SelectTrigger className="h-11 bg-white" data-testid="closing-item-select">
                    <SelectValue placeholder="Select item" />
                  </SelectTrigger>
                  <SelectContent>
                    {items.map((it) => (
                      <SelectItem key={it.id} value={it.id}>
                        <span className="flex items-center gap-2">
                          {it.name}
                          {countedMap[it.id] && (
                            <span className="text-green-600 text-xs">✓</span>
                          )}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="text-xs text-slate-500 mt-1 h-4">
                  {selectedItem
                    ? `${selectedItem.category} · ${selectedItem.unit}`
                    : ""}
                  {selectedItem && countedMap[selectedItem.id] && (
                    <span className="text-orange-600 ml-1">
                      (previously: {countedMap[selectedItem.id].closing_qty} {selectedItem.unit} — will update)
                    </span>
                  )}
                </div>
              </div>

              {/* Shelf Count */}
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">
                  Shelf Count {selectedItem && `(${selectedItem.unit})`}
                </Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={closingQty}
                  onChange={(e) => setClosingQty(e.target.value)}
                  placeholder="0"
                  className="h-11 bg-white tabular-nums"
                  data-testid="closing-qty-input"
                />
                <div className="h-4" />
              </div>

              {/* Notes */}
              <div className="md:col-span-4">
                <Label className="text-sm mb-1.5 block">Notes (optional)</Label>
                <Input
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. spillage, moved to fridge..."
                  className="h-11 bg-white"
                  data-testid="closing-notes-input"
                />
                <div className="h-4" />
              </div>

              {/* Save */}
              <div className="md:col-span-2 flex items-start pt-6">
                <Button
                  type="submit"
                  disabled={saving || !itemId || closingQty === ""}
                  className="w-full h-11 rounded-full bg-orange-600 hover:bg-orange-700 active:scale-95"
                  data-testid="closing-save-btn"
                >
                  {saving ? "Saving..." : "Save Count"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Entries Table */}
      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <ClipboardList size={16} className="text-orange-500" />
            Counts Recorded — {fmtDate(date)}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-4 space-y-2">
              {[1, 2, 3].map((k) => (
                <Skeleton key={k} className="h-12 rounded-xl" />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <Package size={32} className="mx-auto mb-2 opacity-40" />
              <p className="text-sm">No counts recorded for {fmtDate(date)}</p>
              {canRecord && (
                <p className="text-xs mt-1">
                  Select an item above and enter the shelf quantity
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
                    <th className="text-right px-4 py-3">Closing (counted)</th>
                    <th className="text-right px-4 py-3">Consumed</th>
                    <th className="text-left px-4 py-3">Notes</th>
                    <th className="text-left px-4 py-3">Logged at</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr
                      key={e.id}
                      className="border-b border-slate-50 hover:bg-orange-50/30 transition-colors"
                      data-testid={`closing-row-${e.id}`}
                    >
                      <td className="px-4 py-3 font-medium">
                        {e.item_name}
                        <span className="text-xs text-slate-400 ml-1">({e.unit})</span>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-slate-500">
                        {e.opening_qty}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-blue-600 font-medium">
                        +{e.purchased_today}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums font-semibold text-slate-800">
                        {e.closing_qty}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums font-bold text-orange-700">
                        {e.consumed}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500">
                        {e.notes || "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400 whitespace-nowrap">
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
