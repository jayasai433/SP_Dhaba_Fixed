import { useEffect, useMemo, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger }
  from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { Search, Plus, Pencil, Trash2, PackageSearch } from "lucide-react";
import { inr } from "@/lib/format";

const EMPTY = {
  name: "", category: "", base_unit: "",
  default_price: 0,
  units: [{ name: "", conversion_factor: 1, is_default: true }],
  is_active: true,
};

function UnitRow({ row, onChange, onRemove, canRemove }) {
  return (
    <div className="flex items-center gap-2" data-testid="unit-row">
      <Input value={row.name}
        onChange={(e) => onChange({ ...row, name: e.target.value })}
        placeholder="unit (e.g. piece, dozen)" className="h-10 bg-white flex-1" />
      <Input type="number" step="0.001" min="0" value={row.conversion_factor}
        onChange={(e) => onChange({ ...row, conversion_factor: e.target.value })}
        placeholder="factor" className="h-10 bg-white w-24 tabular-nums" />
      <label className="flex items-center gap-1 text-xs text-slate-600 shrink-0">
        <input type="radio" name="default_unit" checked={!!row.is_default}
          onChange={() => onChange({ ...row, is_default: true })} className="accent-orange-600" />
        default
      </label>
      <button type="button" onClick={onRemove} disabled={!canRemove}
        className="text-slate-400 hover:text-red-600 disabled:opacity-30 p-1"
        title="Remove">
        <Trash2 size={16} />
      </button>
    </div>
  );
}

/** ItemDialog: reusable for create + edit. Also exported so Purchases can open it. */
export function ItemDialog({ open, onOpenChange, initial, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [categories, setCategories] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(initial ? {
      ...EMPTY, ...initial,
      units: (initial.units && initial.units.length)
        ? initial.units.map((u) => ({ ...u }))
        : EMPTY.units,
    } : EMPTY);
    api.get("/categories").then(({ data }) => setCategories(data)).catch(() => {});
  }, [open, initial]);

  const updateUnit = (idx, next) => {
    setForm((f) => {
      const units = [...f.units];
      if (next.is_default) units.forEach((u, i) => { u.is_default = i === idx; });
      units[idx] = next;
      return { ...f, units };
    });
  };

  const addUnit = () => setForm((f) => ({
    ...f, units: [...f.units, { name: "", conversion_factor: 1, is_default: false }],
  }));

  const removeUnit = (idx) => setForm((f) => {
    const units = f.units.filter((_, i) => i !== idx);
    if (!units.some((u) => u.is_default) && units.length) units[0].is_default = true;
    return { ...f, units };
  });

  const save = async () => {
    if (!form.name.trim())      return toast.error("Item name is required");
    if (!form.base_unit.trim()) return toast.error("Base unit is required (e.g. piece, kg, L)");
    const cleanUnits = form.units
      .map((u) => ({ name: u.name.trim(), conversion_factor: parseFloat(u.conversion_factor), is_default: !!u.is_default }))
      .filter((u) => u.name && u.conversion_factor > 0);
    if (!cleanUnits.length) return toast.error("Add at least one unit");
    if (!cleanUnits.some((u) => u.name.toLowerCase() === form.base_unit.trim().toLowerCase())) {
      cleanUnits.push({ name: form.base_unit.trim(), conversion_factor: 1, is_default: !cleanUnits.some((u) => u.is_default) });
    }
    if (!cleanUnits.some((u) => u.is_default)) cleanUnits[0].is_default = true;

    const payload = {
      name: form.name.trim(),
      category: form.category || "",
      base_unit: form.base_unit.trim(),
      default_price: parseFloat(form.default_price) || 0,
      units: cleanUnits,
    };

    setSaving(true);
    try {
      let saved;
      if (form.id) {
        const { data } = await api.patch(`/items/${form.id}`, { ...payload, is_active: form.is_active });
        saved = data; toast.success("Item updated");
      } else {
        const { data } = await api.post("/items", payload);
        saved = data; toast.success("Item added");
      }
      onOpenChange(false);
      onSaved?.(saved);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="item-dialog">
        <DialogHeader>
          <DialogTitle>{form.id ? "Edit item" : "Add item"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label className="text-sm mb-1.5 block">Item name</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Eggs, Chicken, Basmati Rice" className="h-11 bg-white"
              data-testid="item-name-input" autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm mb-1.5 block">Category</Label>
              <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                <SelectTrigger className="h-11 bg-white" data-testid="item-category-select">
                  <SelectValue placeholder="None" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((c) => (
                    <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm mb-1.5 block">Base unit</Label>
              <Input value={form.base_unit}
                onChange={(e) => setForm({ ...form, base_unit: e.target.value })}
                placeholder="piece / kg / L" className="h-11 bg-white"
                data-testid="item-base-unit-input" />
            </div>
          </div>
          <div>
            <Label className="text-sm mb-1.5 block">Default price per base unit (₹)</Label>
            <Input type="number" step="0.01" min="0" value={form.default_price}
              onChange={(e) => setForm({ ...form, default_price: e.target.value })}
              className="h-11 bg-white tabular-nums" data-testid="item-default-price-input" />
          </div>

          <div className="pt-2">
            <div className="flex items-center justify-between mb-2">
              <Label className="text-sm">Units allowed</Label>
              <button type="button" onClick={addUnit}
                className="text-xs text-orange-700 font-medium hover:underline"
                data-testid="add-unit-button">
                + Add unit
              </button>
            </div>
            <p className="text-[11px] text-slate-500 mb-2">
              How many base units in one of this unit? e.g. base = piece, dozen = 12, tray = 30.
            </p>
            <div className="space-y-2">
              {form.units.map((u, i) => (
                <UnitRow key={i} row={u}
                  onChange={(next) => updateUnit(i, next)}
                  onRemove={() => removeUnit(i)}
                  canRemove={form.units.length > 1} />
              ))}
            </div>
          </div>

          {form.id && (
            <label className="flex items-center gap-2 text-sm text-slate-700 pt-1">
              <input type="checkbox" checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="accent-orange-600" />
              Active
            </label>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={save} disabled={saving} data-testid="item-dialog-save"
            className="bg-orange-600 hover:bg-orange-700">
            {saving ? "Saving..." : (form.id ? "Save changes" : "Add item")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Items() {
  const { user } = useAuth();
  const canEdit = ["admin", "staff"].includes(user.role);
  const canDelete = user.role === "admin";

  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/items", { params: { include_inactive: true } });
      setItems(data);
    } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return items;
    return items.filter((i) => i.name.toLowerCase().includes(query) || (i.category || "").toLowerCase().includes(query));
  }, [items, q]);

  const openNew = () => { setEditing(null); setOpen(true); };
  const openEdit = (it) => { setEditing(it); setOpen(true); };
  const remove = async (it) => {
    if (!window.confirm(`Deactivate "${it.name}"? History stays intact.`)) return;
    try { await api.delete(`/items/${it.id}`); toast.success("Item deactivated"); load(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  return (
    <div className="space-y-5 animate-fade-up" data-testid="items-page">
      {/* Sticky totals bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Master data</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Items</h1>
          <p className="text-slate-600 text-sm mt-0.5">
            {items.length} total. {items.filter((i) => i.is_active).length} active
          </p>
        </div>
        {canEdit && (
          <Button onClick={openNew} data-testid="items-add-button"
            className="rounded-full bg-orange-600 hover:bg-orange-700 h-11 px-5 shadow-sm">
            <Plus size={16} className="mr-1" />Add item
          </Button>
        )}
      </div>

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-4 md:p-5">
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <Input value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search by name or category" className="pl-9 h-11 bg-white"
              data-testid="items-search" />
          </div>

          {filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-500" data-testid="items-empty-state">
              <PackageSearch className="mx-auto text-orange-300 mb-2" size={36} />
              <p className="font-medium">
                {items.length === 0 ? "No items yet" : "No matches for your search"}
              </p>
              {items.length === 0 && canEdit && (
                <p className="text-sm mt-1">Tap the add button to create your first item.</p>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Item</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Base</TableHead>
                    <TableHead>Allowed units</TableHead>
                    <TableHead className="text-right">Default price</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((it) => (
                    <TableRow key={it.id} data-testid={`item-row-${it.id}`}
                      className={!it.is_active ? "opacity-50" : ""}>
                      <TableCell className="font-medium">{it.name}</TableCell>
                      <TableCell className="text-slate-600">{it.category || "."}</TableCell>
                      <TableCell className="text-slate-600">{it.base_unit}</TableCell>
                      <TableCell className="text-xs text-slate-600">
                        {(it.units || []).map((u) => `${u.name} (×${u.conversion_factor})`).join(", ")}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{inr(it.default_price || 0)}</TableCell>
                      <TableCell className="text-right">
                        {canEdit && (
                          <button onClick={() => openEdit(it)} data-testid={`item-edit-${it.id}`}
                            className="text-slate-500 hover:text-orange-700 p-2">
                            <Pencil size={14} />
                          </button>
                        )}
                        {canDelete && it.is_active && (
                          <button onClick={() => remove(it)} data-testid={`item-delete-${it.id}`}
                            className="text-slate-400 hover:text-red-600 p-2">
                            <Trash2 size={14} />
                          </button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <ItemDialog open={open} onOpenChange={setOpen} initial={editing}
        onSaved={() => load()} />
    </div>
  );
}
