import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { Save } from "lucide-react";

export default function ReorderPane() {
  const [items, setItems] = useState([]);
  const [edits, setEdits] = useState({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const { data } = await api.get("/items");
    setItems(data.filter((i) => i.is_active));
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    const updates = Object.entries(edits).map(([item_id, reorder_level]) => ({
      item_id, reorder_level: parseFloat(reorder_level),
    }));
    if (updates.length === 0) return toast.info("No changes to save");
    setSaving(true);
    try {
      await api.post("/items/bulk-reorder", { updates });
      toast.success(`${updates.length} items updated`);
      setEdits({});
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  };

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm mt-4">
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm text-slate-600">Update reorder levels for all active items at once.</p>
          <Button onClick={save} disabled={saving} data-testid="reorder-save-all" className="rounded-full bg-orange-600 hover:bg-orange-700">
            <Save size={16} className="mr-1" />{saving ? "Saving..." : "Save All"}
          </Button>
        </div>
        <Table>
          <TableHeader><TableRow>
            <TableHead>Item</TableHead><TableHead>Category</TableHead>
            <TableHead>Unit</TableHead><TableHead className="text-right">Reorder Level</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {items.map((it) => (
              <TableRow key={it.id} data-testid={`reorder-row-${it.id}`}>
                <TableCell className="font-medium">{it.name}</TableCell>
                <TableCell className="text-slate-600">{it.category}</TableCell>
                <TableCell className="text-slate-600">{it.unit}</TableCell>
                <TableCell className="text-right">
                  <Input type="number" min="0" step="0.01" data-testid={`reorder-input-${it.id}`}
                    defaultValue={it.reorder_level}
                    onChange={(e) => setEdits((p) => ({ ...p, [it.id]: e.target.value }))}
                    className="h-9 w-24 ml-auto tabular-nums text-right" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
