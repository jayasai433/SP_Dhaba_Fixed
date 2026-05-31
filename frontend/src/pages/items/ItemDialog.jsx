import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

export default function ItemDialog({ open, onOpenChange, initial, categories, units, onSave }) {
  const [form, setForm] = useState(initial);
  useEffect(() => { setForm(initial); }, [initial]);
  if (!form) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl" data-testid="item-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">{form.id ? "Edit Item" : "Add New Item"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label className="text-sm mb-1 block">Name</Label>
            <Input data-testid="item-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-11" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm mb-1 block">Category</Label>
              <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                <SelectTrigger data-testid="item-category-select" className="h-11"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>
                  {categories.map((c) => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm mb-1 block">Unit</Label>
              <Select value={form.unit} onValueChange={(v) => setForm({ ...form, unit: v })}>
                <SelectTrigger data-testid="item-unit-select" className="h-11"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>
                  {units.map((u) => <SelectItem key={u.id} value={u.name}>{u.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label className="text-sm mb-1 block">Reorder Level</Label>
            <Input type="number" min="0" step="0.01" data-testid="item-reorder-input"
              value={form.reorder_level} onChange={(e) => setForm({ ...form, reorder_level: e.target.value })} className="h-11 tabular-nums" />
          </div>
          {form.id && (
            <div className="flex items-center justify-between p-3 rounded-xl bg-orange-50">
              <Label htmlFor="item-active" className="text-sm">Active (visible in dropdowns)</Label>
              <Switch id="item-active" data-testid="item-active-switch" checked={form.is_active}
                onCheckedChange={(v) => setForm({ ...form, is_active: v })} />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="rounded-full">Cancel</Button>
          <Button onClick={() => onSave(form)} data-testid="item-save-button" className="rounded-full bg-orange-600 hover:bg-orange-700">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
