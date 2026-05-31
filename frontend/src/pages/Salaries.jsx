import { useEffect, useMemo, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { inr, fmtDate, todayIST } from "@/lib/format";
import { Plus, CheckCircle2, Users } from "lucide-react";

function currentMonth() { return todayIST().slice(0, 7); }

export default function Salaries() {
  const [staff, setStaff] = useState([]);
  const [rows, setRows] = useState([]);
  const [month, setMonth] = useState(currentMonth());
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ staff_id: "", basic_salary: "", advance_paid: "0", notes: "" });
  const [payOpen, setPayOpen] = useState(null);
  const [paidDate, setPaidDate] = useState(todayIST());

  const loadStaff = () => api.get("/staff").then(({ data }) => setStaff(data));
  const load = () => api.get("/salaries", { params: { month } }).then(({ data }) => setRows(data));
  useEffect(() => { loadStaff(); }, []);
  useEffect(() => { load(); }, [month]);

  const activeStaff = staff.filter((s) => s.is_active);

  const openNew = () => {
    setForm({ staff_id: activeStaff[0]?.id || "", basic_salary: activeStaff[0]?.default_salary || "", advance_paid: "0", notes: "" });
    setOpen(true);
  };

  const save = async () => {
    if (!form.staff_id) return toast.error("Select staff");
    if (!(parseFloat(form.basic_salary) >= 0)) return toast.error("Invalid basic salary");
    try {
      await api.post("/salaries", {
        staff_id: form.staff_id, month,
        basic_salary: parseFloat(form.basic_salary || 0),
        advance_paid: parseFloat(form.advance_paid || 0),
        notes: form.notes || "",
      });
      toast.success("Salary entry added");
      setOpen(false); load();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const pay = async () => {
    try {
      await api.post(`/salaries/${payOpen.id}/pay`, { paid_date: paidDate });
      toast.success("Marked as paid");
      setPayOpen(null); load();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const totals = useMemo(() => {
    const total = rows.reduce((a, b) => a + (b.net_payable || 0), 0);
    const paid = rows.filter((r) => r.paid_date).reduce((a, b) => a + (b.net_payable || 0), 0);
    return { total, paid, pending: total - paid };
  }, [rows]);

  return (
    <div className="space-y-6 animate-fade-up" data-testid="salaries-page">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Payroll</div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Salaries</h1>
          <p className="text-slate-600 text-sm mt-1">Monthly salary tracking for staff</p>
        </div>
        <div className="flex gap-2 items-end">
          <div>
            <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">Month</Label>
            <Input type="month" data-testid="salary-month-input" value={month} onChange={(e) => setMonth(e.target.value)} className="h-11 bg-white" />
          </div>
          <Button onClick={openNew} data-testid="salary-add-button" className="rounded-full bg-orange-600 hover:bg-orange-700 h-11">
            <Plus size={16} className="mr-1" />Add Entry
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="rounded-2xl border-orange-900/10 shadow-sm"><CardContent className="p-4">
          <div className="text-xs uppercase tracking-wider text-slate-500">Total Payroll</div>
          <div className="font-display font-bold text-2xl text-slate-900 tabular-nums" data-testid="salary-total">{inr(totals.total)}</div>
        </CardContent></Card>
        <Card className="rounded-2xl border-green-200 shadow-sm bg-green-50/40"><CardContent className="p-4">
          <div className="text-xs uppercase tracking-wider text-green-700">Paid</div>
          <div className="font-display font-bold text-2xl text-green-800 tabular-nums" data-testid="salary-paid">{inr(totals.paid)}</div>
        </CardContent></Card>
        <Card className="rounded-2xl border-amber-200 shadow-sm bg-amber-50/40"><CardContent className="p-4">
          <div className="text-xs uppercase tracking-wider text-amber-700">Pending</div>
          <div className="font-display font-bold text-2xl text-amber-800 tabular-nums" data-testid="salary-pending">{inr(totals.pending)}</div>
        </CardContent></Card>
      </div>

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          {rows.length === 0 ? (
            <div className="text-center py-10 text-slate-500">
              <Users className="mx-auto text-orange-300 mb-2" size={36} />
              <p>No salary entries for {month}.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Staff</TableHead>
                    <TableHead className="text-right">Basic</TableHead>
                    <TableHead className="text-right">Advance</TableHead>
                    <TableHead className="text-right">Net Payable</TableHead>
                    <TableHead>Paid Date</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id} data-testid={`salary-row-${r.id}`}>
                      <TableCell className="font-medium">{r.staff_name}</TableCell>
                      <TableCell className="text-right tabular-nums">{inr(r.basic_salary)}</TableCell>
                      <TableCell className="text-right tabular-nums">{inr(r.advance_paid)}</TableCell>
                      <TableCell className="text-right tabular-nums font-semibold">{inr(r.net_payable)}</TableCell>
                      <TableCell>
                        {r.paid_date ? (
                          <Badge className="bg-green-600 hover:bg-green-600">Paid · {fmtDate(r.paid_date)}</Badge>
                        ) : (
                          <Badge className="bg-amber-500 hover:bg-amber-500">Pending</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-slate-500">{r.notes || "—"}</TableCell>
                      <TableCell>
                        {!r.paid_date && (
                          <Button size="sm" variant="outline" data-testid={`salary-pay-${r.id}`}
                            onClick={() => { setPayOpen(r); setPaidDate(todayIST()); }}
                            className="rounded-full border-orange-200 text-orange-700 hover:bg-orange-50">
                            <CheckCircle2 size={14} className="mr-1" />Mark Paid
                          </Button>
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

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-2xl">
          <DialogHeader><DialogTitle className="font-display">Add Salary — {month}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Staff</Label>
              <Select value={form.staff_id} onValueChange={(v) => {
                const s = staff.find((x) => x.id === v);
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
                {inr((parseFloat(form.basic_salary || 0) - parseFloat(form.advance_paid || 0)) || 0)}
              </div>
            </div>
            <div>
              <Label>Notes</Label>
              <Input data-testid="salary-notes-input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="h-11" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="rounded-full">Cancel</Button>
            <Button onClick={save} data-testid="salary-save-button" className="rounded-full bg-orange-600 hover:bg-orange-700">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!payOpen} onOpenChange={(o) => !o && setPayOpen(null)}>
        <DialogContent className="rounded-2xl">
          <DialogHeader><DialogTitle className="font-display">Mark as Paid — {payOpen?.staff_name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Paid Date</Label>
              <Input type="date" data-testid="salary-paid-date" value={paidDate} onChange={(e) => setPaidDate(e.target.value)} className="h-11" />
            </div>
            <div className="text-sm text-slate-600">
              Net payable: <b className="tabular-nums">{inr(payOpen?.net_payable || 0)}</b>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPayOpen(null)} className="rounded-full">Cancel</Button>
            <Button onClick={pay} data-testid="salary-pay-confirm" className="rounded-full bg-green-600 hover:bg-green-700">Confirm Paid</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
