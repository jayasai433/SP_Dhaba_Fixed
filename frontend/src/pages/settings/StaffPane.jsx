import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus } from "lucide-react";

export default function StaffPane() {
  const [rows, setRows] = useState([]);
  const [openNew, setOpenNew] = useState(false);
  const [form, setForm] = useState({ name: "", default_salary: "0", phone: "" });

  const load = useCallback(async () => {
    const { data } = await api.get("/staff");
    setRows(data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!form.name.trim()) return toast.error("Name required");
    try {
      await api.post("/staff", {
        name: form.name.trim(),
        default_salary: parseFloat(form.default_salary || 0),
        phone: form.phone || "",
      });
      setOpenNew(false);
      setForm({ name: "", default_salary: "0", phone: "" });
      load();
      toast.success("Staff added");
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const update = async (s, patch) => {
    try { await api.patch(`/staff/${s.id}`, patch); load(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm mt-4">
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm text-slate-600">Manage staff who appear in the Salary Tracker. Owner is not on payroll.</p>
          <Button onClick={() => setOpenNew(true)} data-testid="staff-add-button" className="rounded-full bg-orange-600 hover:bg-orange-700">
            <Plus size={16} className="mr-1" />Add Staff
          </Button>
        </div>
        <Table>
          <TableHeader><TableRow>
            <TableHead>Name</TableHead><TableHead>Phone</TableHead>
            <TableHead className="text-right">Default Salary</TableHead><TableHead>Active</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {rows.map((s) => (
              <TableRow key={s.id} data-testid={`staff-row-${s.id}`}>
                <TableCell className="font-medium">{s.name}</TableCell>
                <TableCell className="text-slate-600">{s.phone || "—"}</TableCell>
                <TableCell className="text-right">
                  <Input type="number" min="0" step="0.01" defaultValue={s.default_salary}
                    onBlur={(e) => {
                      const v = parseFloat(e.target.value);
                      if (!Number.isNaN(v) && v !== s.default_salary) update(s, { default_salary: v });
                    }}
                    data-testid={`staff-salary-${s.id}`} className="h-9 w-32 ml-auto tabular-nums text-right" />
                </TableCell>
                <TableCell>
                  <Switch checked={s.is_active} onCheckedChange={(v) => update(s, { is_active: v })} data-testid={`staff-active-${s.id}`} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <Dialog open={openNew} onOpenChange={setOpenNew}>
          <DialogContent className="rounded-2xl">
            <DialogHeader><DialogTitle className="font-display">Add Staff</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>Name</Label><Input data-testid="new-staff-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-11" /></div>
              <div><Label>Phone</Label><Input data-testid="new-staff-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="h-11" /></div>
              <div><Label>Default Monthly Salary (₹)</Label><Input type="number" min="0" step="0.01" data-testid="new-staff-salary"
                value={form.default_salary} onChange={(e) => setForm({ ...form, default_salary: e.target.value })} className="h-11 tabular-nums" /></div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpenNew(false)} className="rounded-full">Cancel</Button>
              <Button onClick={save} data-testid="new-staff-save" className="rounded-full bg-orange-600 hover:bg-orange-700">Save</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
