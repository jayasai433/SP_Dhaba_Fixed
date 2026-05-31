import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { inr } from "@/lib/format";

export default function AddSalaryDialog({ open, onOpenChange, month, activeStaff, onSave }) {
  const [form, setForm] = useState({ staff_id: "", basic_salary: "", advance_paid: "0", notes: "" });

  useEffect(() => {
    if (open) {
      const s = activeStaff[0];
      setForm({ staff_id: s?.id || "", basic_salary: s?.default_salary || "", advance_paid: "0", notes: "" });
    }
  }, [open, activeStaff]);

  const net = (parseFloat(form.basic_salary || 0) - parseFloat(form.advance_paid || 0)) || 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl">
        <DialogHeader><DialogTitle className="font-display">Add Salary — {month}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>Staff</Label>
            <Select value={form.staff_id} onValueChange={(v) => {
              const s = activeStaff.find((x) => x.id === v);
              setForm({ ...form, staff_id: v, basic_salary: s?.default_salary || "" });
            }}>
              <SelectTrigger data-testid="salary-staff-select" className="h-11"><SelectValue /></SelectTrigger>
              <SelectContent>
                {activeStaff.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Basic Salary (₹)</Label>
              <Input type="number" min="0" step="0.01" data-testid="salary-basic-input"
                value={form.basic_salary} onChange={(e) => setForm({ ...form, basic_salary: e.target.value })}
                className="h-11 tabular-nums" />
            </div>
            <div>
              <Label>Advance Paid (₹)</Label>
              <Input type="number" min="0" step="0.01" data-testid="salary-advance-input"
                value={form.advance_paid} onChange={(e) => setForm({ ...form, advance_paid: e.target.value })}
                className="h-11 tabular-nums" />
            </div>
          </div>
          <div className="p-3 rounded-xl bg-orange-50">
            <div className="text-xs uppercase tracking-wider text-orange-700">Net Payable</div>
            <div className="font-display font-bold text-xl text-orange-700 tabular-nums" data-testid="salary-net-preview">
              {inr(net)}
            </div>
          </div>
          <div>
            <Label>Notes</Label>
            <Input data-testid="salary-notes-input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="h-11" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="rounded-full">Cancel</Button>
          <Button onClick={() => onSave(form)} data-testid="salary-save-button" className="rounded-full bg-orange-600 hover:bg-orange-700">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
