import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { SKELETON_KEYS } from "@/lib/skeletons";
import { toast } from "sonner";
import { Plus, Truck } from "lucide-react";

const EMPTY = { name: "", phone: "", address: "", items: "", notes: "" };

export default function SupplierPane() {
  const [rows, setRows] = useState(null);
  const [openNew, setOpenNew] = useState(false);
  const [editing, setEditing] = useState(null); // supplier object being edited, or null
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/suppliers", { params: { include_inactive: true } });
      setRows(data);
    } catch (err) { toast.error(formatApiError(err)); setRows([]); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const startEdit = (s) => { setEditing(s); setForm({ name: s.name, phone: s.phone || "", address: s.address || "", items: s.items || "", notes: s.notes || "" }); setOpenNew(true); };
  const startNew  = () => { setEditing(null); setForm(EMPTY); setOpenNew(true); };

  const save = async () => {
    if (!form.name.trim()) return toast.error("Supplier name required");
    setSaving(true);
    try {
      if (editing) {
        await api.patch(`/suppliers/${editing.id}`, form);
        toast.success("Supplier updated");
      } else {
        await api.post("/suppliers", form);
        toast.success("Supplier added");
      }
      setOpenNew(false); setForm(EMPTY); setEditing(null); load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  };

  const toggleActive = async (s, is_active) => {
    try { await api.patch(`/suppliers/${s.id}`, { is_active }); load(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const remove = async (s) => {
    if (!window.confirm(`Remove supplier "${s.name}"? It will be marked inactive.`)) return;
    try { await api.delete(`/suppliers/${s.id}`); toast.success("Supplier removed"); load(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm mt-4" data-testid="suppliers-pane">
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3 gap-2">
          <p className="text-sm text-slate-600">Vendor directory — link suppliers to purchases for traceability and payment tracking.</p>
          <Button onClick={startNew} data-testid="supplier-add-button" className="rounded-full bg-orange-600 hover:bg-orange-700 shrink-0">
            <Plus size={16} className="mr-1" />Add Supplier
          </Button>
        </div>

        {rows === null ? (
          <div className="space-y-2">{SKELETON_KEYS.slice(0, 4).map((k) => <Skeleton key={k} className="h-12 rounded-lg" />)}</div>
        ) : rows.length === 0 ? (
          <div className="text-center py-10 text-slate-500">
            <Truck className="mx-auto text-orange-300 mb-2" size={36} />
            <p className="font-medium">No suppliers yet</p>
            <p className="text-sm mt-1">Add your first supplier to start tracking vendor purchases.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Name</TableHead><TableHead>Phone</TableHead>
                <TableHead>Items</TableHead><TableHead>Active</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {rows.map((s) => (
                  <TableRow key={s.id} data-testid={`supplier-row-${s.id}`}>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell className="text-slate-600 tabular-nums">{s.phone || "—"}</TableCell>
                    <TableCell className="text-slate-600 text-sm max-w-[260px] truncate" title={s.items || ""}>{s.items || "—"}</TableCell>
                    <TableCell>
                      <Switch checked={s.is_active} onCheckedChange={(v) => toggleActive(s, v)} data-testid={`supplier-active-${s.id}`} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" className="rounded-full text-orange-700"
                        data-testid={`supplier-edit-${s.id}`} onClick={() => startEdit(s)}>Edit</Button>
                      <Button variant="ghost" size="sm" className="rounded-full text-red-600"
                        data-testid={`supplier-remove-${s.id}`} onClick={() => remove(s)}>Remove</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <Dialog open={openNew} onOpenChange={(o) => { setOpenNew(o); if (!o) { setEditing(null); setForm(EMPTY); } }}>
          <DialogContent className="rounded-2xl max-w-lg">
            <DialogHeader><DialogTitle className="font-display">{editing ? "Edit Supplier" : "Add Supplier"}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>Name *</Label><Input data-testid="supplier-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-11" placeholder="e.g. Sharma Dairy" /></div>
              <div><Label>Phone</Label><Input data-testid="supplier-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="h-11 tabular-nums" placeholder="+91 9XXXXXXXXX" /></div>
              <div><Label>Address</Label><Textarea data-testid="supplier-address-input" rows={2} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></div>
              <div>
                <Label>Items supplied</Label>
                <Textarea data-testid="supplier-items-input" rows={2} value={form.items}
                  onChange={(e) => setForm({ ...form, items: e.target.value })}
                  placeholder="Comma-separated, e.g. Paneer, Milk, Curd" />
              </div>
              <div><Label>Notes</Label><Textarea data-testid="supplier-notes-input" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpenNew(false)} className="rounded-full">Cancel</Button>
              <Button onClick={save} disabled={saving} data-testid="supplier-save" className="rounded-full bg-orange-600 hover:bg-orange-700">
                {saving ? "Saving..." : "Save"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
