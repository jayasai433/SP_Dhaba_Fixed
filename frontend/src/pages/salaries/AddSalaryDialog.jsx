import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

export default function AddSalaryDialog({ open, onOpenChange, onSave, activeStaff, month }) {
  const [form, setForm] = useState({ staff_id: "", basic_salary: "", advance_paid: "0", notes: "" });
  const [isMidMonth, setIsMidMonth] = useState(false);
  const [joiningDate, setJoiningDate] = useState("");

  useEffect(() => {
    if (open) {
      const s = activeStaff[0];
      setForm({ staff_id: s?.id || "", basic_salary: s?.default_salary || "", advance_paid: "0", notes: "" });
      setIsMidMonth(false);
      setJoiningDate("");
    }
  }, [open, activeStaff]);

  // Prorate preview calculation
  const daysInMonth = new Date(month + "-01") 
    ? new Date(new Date(month + "-01").getFullYear(), new Date(month + "-01").getMonth() + 1, 0).getDate()
    : 30;
  
  const joiningDay = joiningDate ? new Date(joiningDate).getDate() : 1;
  const workingDays = isMidMonth && joiningDate ? daysInMonth - joiningDay + 1 : daysInMonth;
  const proratedSalary = isMidMonth && joiningDate
    ? Math.round((parseFloat(form.basic_salary || 0) * workingDays / daysInMonth) * 100) / 100
    : parseFloat(form.basic_salary || 0);
  const net = (proratedSalary - parseFloat(form.advance_paid || 0)) || 0;

  const handleSave = () => {
    onSave({
      ...form,
      basic_salary: parseFloat(form.basic_salary),
      advance_paid: parseFloat(form.advance_paid || 0),
      joining_date: isMidMonth && joiningDate ? joiningDate : null,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl">
        <DialogHeader>
          <DialogTitle className="font-display">Add Salary — {month}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          {/* Staff select */}
          <div>
            <Label className="text-sm mb-1 block">Staff Member</Label>
            <Select value={form.staff_id}
              onValueChange={(v) => {
                const s = activeStaff.find((x) => x.id === v);
                setForm((p) => ({ ...p, staff_id: v, basic_salary: s?.default_salary || p.basic_salary }));
              }}>
              <SelectTrigger className="h-10"><SelectValue placeholder="Select staff" /></SelectTrigger>
              <SelectContent>
                {activeStaff.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {/* Basic salary */}
          <div>
            <Label className="text-sm mb-1 block">Monthly Salary (₹)</Label>
            <Input type="number" value={form.basic_salary}
              onChange={(e) => setForm((p) => ({ ...p, basic_salary: e.target.value }))}
              className="h-10 tabular-nums" placeholder="0" />
          </div>

          {/* Mid-month joining toggle */}
          <div className="flex items-center gap-3 py-1">
            <Switch checked={isMidMonth} onCheckedChange={setIsMidMonth} id="mid-month" />
            <Label htmlFor="mid-month" className="text-sm cursor-pointer">
              Staff joined mid-month (prorate salary)
            </Label>
          </div>

          {/* Joining date — only shown when toggle is on */}
          {isMidMonth && (
            <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 space-y-2">
              <div>
                <Label className="text-sm mb-1 block">Joining Date</Label>
                <Input type="date" value={joiningDate}
                  onChange={(e) => setJoiningDate(e.target.value)}
                  min={month + "-01"}
                  max={month + "-" + String(daysInMonth).padStart(2, "0")}
                  className="h-10 bg-white" />
              </div>
              {joiningDate && (
                <div className="text-sm text-orange-700 font-medium">
                  Working days: {workingDays} of {daysInMonth} days
                  <span className="ml-2 text-slate-600 font-normal">
                    → Prorated salary: ₹{proratedSalary.toLocaleString("en-IN")}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Advance */}
          <div>
            <Label className="text-sm mb-1 block">Advance Already Paid (₹)</Label>
            <Input type="number" value={form.advance_paid}
              onChange={(e) => setForm((p) => ({ ...p, advance_paid: e.target.value }))}
              className="h-10 tabular-nums" placeholder="0" />
          </div>

          {/* Notes */}
          <div>
            <Label className="text-sm mb-1 block">Notes (optional)</Label>
            <Input value={form.notes}
              onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
              className="h-10" placeholder="e.g. joined 15th June" />
          </div>

          {/* Net payable preview */}
          <div className="bg-slate-50 rounded-xl px-4 py-3 flex justify-between items-center">
            <span className="text-sm text-slate-600">Net Payable</span>
            <span className="font-display font-bold text-xl text-orange-700 tabular-nums">
              ₹{net.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </span>
          </div>

          <Button onClick={handleSave}
            className="w-full rounded-full bg-orange-600 hover:bg-orange-700 active:scale-95">
            Save Salary Entry
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
