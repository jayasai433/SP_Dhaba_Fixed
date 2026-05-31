import { useEffect, useMemo, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { Search, Plus, Pencil } from "lucide-react";
import ItemDialog from "@/pages/items/ItemDialog";

const EMPTY_ITEM = { name: "", category: "", unit: "", reorder_level: 0, is_active: true };

export default function Items() {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [units, setUnits] = useState([]);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    const [it, ca, un] = await Promise.all([
      api.get("/items"), api.get("/categories"), api.get("/units"),
    ]);
    setItems(it.data); setCategories(ca.data); setUnits(un.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => items
    .filter((i) => !q || i.name.toLowerCase().includes(q.toLowerCase()))
    .filter((i) => cat === "all" || i.category === cat),
    [items, q, cat]);

  const openNew = () => { setEditing({ ...EMPTY_ITEM }); setOpen(true); };
  const openEdit = (it) => { setEditing({ ...it }); setOpen(true); };

  const save = async (form) => {
    if (!form.name?.trim()) return toast.error("Name required");
    if (!form.category) return toast.error("Category required");
    if (!form.unit) return toast.error("Unit required");
    try {
      if (form.id) {
        await api.patch(`/items/${form.id}`, {
          name: form.name, category: form.category, unit: form.unit,
          reorder_level: parseFloat(form.reorder_level), is_active: form.is_active,
        });
        toast.success("Item updated");
      } else {
        await api.post("/items", {
          name: form.name, category: form.category, unit: form.unit,
          reorder_level: parseFloat(form.reorder_level || 0),
        });
        toast.success("Item added");
      }
      setOpen(false); setEditing(null); load();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  return (
    <div className="space-y-6 animate-fade-up" data-testid="items-page">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Configuration</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Item Master</h1>
          <p className="text-slate-600 text-sm mt-1">{items.length} items · {items.filter((i) => i.is_active).length} active</p>
        </div>
        <Button onClick={openNew} data-testid="items-add-button" className="rounded-full bg-orange-600 hover:bg-orange-700">
          <Plus size={16} className="mr-1" />Add Item
        </Button>
      </div>

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <div className="flex flex-col md:flex-row gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <Input data-testid="items-search" value={q} onChange={(e) => setQ(e.target.value)}
                placeholder="Search items..." className="pl-9 h-11 bg-white" />
            </div>
            <Select value={cat} onValueChange={setCat}>
              <SelectTrigger data-testid="items-filter-cat" className="h-11 w-full md:w-56 bg-white"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {categories.map((c) => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead><TableHead>Category</TableHead><TableHead>Unit</TableHead>
                  <TableHead className="text-right">Reorder Level</TableHead><TableHead>Active</TableHead><TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((it) => (
                  <TableRow key={it.id} data-testid={`item-row-${it.id}`} className={!it.is_active ? "opacity-50" : ""}>
                    <TableCell className="font-medium">{it.name}</TableCell>
                    <TableCell className="text-slate-600">{it.category}</TableCell>
                    <TableCell className="text-slate-600">{it.unit}</TableCell>
                    <TableCell className="text-right tabular-nums">{it.reorder_level}</TableCell>
                    <TableCell>{it.is_active ? <span className="text-green-700 text-xs font-semibold">Active</span> : <span className="text-slate-400 text-xs">Inactive</span>}</TableCell>
                    <TableCell>
                      <Button size="sm" variant="ghost" onClick={() => openEdit(it)} data-testid={`item-edit-${it.id}`}><Pencil size={14} /></Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <ItemDialog
        open={open} onOpenChange={setOpen}
        initial={editing} categories={categories} units={units} onSave={save}
      />
    </div>
  );
}
