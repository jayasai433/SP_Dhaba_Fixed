import { useEffect, useMemo, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { inr, fmtDate, todayIST } from "@/lib/format";
import { Plus, CheckCircle2, Users } from "lucide-react";
import AddSalaryDialog from "@/pages/salaries/AddSalaryDialog";
import MarkPaidDialog from "@/pages/salaries/MarkPaidDialog";

function currentMonth() { return todayIST().slice(0, 7); }

function SummaryCards({ total, paid, pending }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      <Card className="rounded-2xl border-orange-900/10 shadow-sm"><CardContent className="p-4">
        <div className="text-xs uppercase tracking-wider text-slate-500">Total Payroll</div>
        <div className="font-display font-bold text-2xl text-slate-900 tabular-nums" data-testid="salary-total">{inr(total)}</div>
      </CardContent></Card>
      <Card className="rounded-2xl border-green-200 shadow-sm bg-green-50/40"><CardContent className="p-4">
        <div className="text-xs uppercase tracking-wider text-green-700">Paid</div>
        <div className="font-display font-bold text-2xl text-green-800 tabular-nums" data-testid="salary-paid">{inr(paid)}</div>
      </CardContent></Card>
      <Card className="rounded-2xl border-amber-200 shadow-sm bg-amber-50/40"><CardContent className="p-4">
        <div className="text-xs uppercase tracking-wider text-amber-700">Pending</div>
        <div className="font-display font-bold text-2xl text-amber-800 tabular-nums" data-testid="salary-pending">{inr(pending)}</div>
      </CardContent></Card>
    </div>
  );
}

function SalaryTable({ rows, onPay }) {
  if (rows.length === 0) {
    return (
      <div className="text-center py-10 text-slate-500">
        <Users className="mx-auto text-orange-300 mb-2" size={36} />
        <p>No salary entries this month.</p>
      </div>
    );
  }
  return (
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
                {r.paid_date
                  ? <Badge className="bg-green-600 hover:bg-green-600">Paid · {fmtDate(r.paid_date)}</Badge>
                  : <Badge className="bg-amber-500 hover:bg-amber-500">Pending</Badge>}
              </TableCell>
              <TableCell className="text-xs text-slate-500">{r.notes || "—"}</TableCell>
              <TableCell>
                {!r.paid_date && (
                  <Button size="sm" variant="outline" data-testid={`salary-pay-${r.id}`}
                    onClick={() => onPay(r)}
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
  );
}

export default function Salaries() {
  const [staff, setStaff] = useState([]);
  const [rows, setRows] = useState([]);
  const [month, setMonth] = useState(currentMonth());
  const [open, setOpen] = useState(false);
  const [payOpen, setPayOpen] = useState(null);

  const loadStaff = useCallback(async () => {
    try {
      const { data } = await api.get("/staff");
      setStaff(data);
    } catch (err) { console.error("Failed to load staff:", err); }
  }, []);
  const loadRows = useCallback(async () => {
    try {
      const { data } = await api.get("/salaries", { params: { month } });
      setRows(data);
    } catch (err) { console.error("Failed to load salaries:", err); }
  }, [month]);

  useEffect(() => { loadStaff(); }, [loadStaff]);
  useEffect(() => { loadRows(); }, [loadRows]);

  const activeStaff = useMemo(() => staff.filter((s) => s.is_active), [staff]);

  const save = async (form) => {
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
      setOpen(false); loadRows();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const confirmPay = async (paidDate) => {
    try {
      await api.post(`/salaries/${payOpen.id}/pay`, { paid_date: paidDate });
      toast.success("Marked as paid");
      setPayOpen(null); loadRows();
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
          <Button onClick={() => setOpen(true)} data-testid="salary-add-button" className="rounded-full bg-orange-600 hover:bg-orange-700 h-11">
            <Plus size={16} className="mr-1" />Add Entry
          </Button>
        </div>
      </div>

      <SummaryCards total={totals.total} paid={totals.paid} pending={totals.pending} />

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <SalaryTable rows={rows} onPay={setPayOpen} />
        </CardContent>
      </Card>

      <AddSalaryDialog
        open={open} onOpenChange={setOpen}
        month={month} activeStaff={activeStaff} onSave={save}
      />
      <MarkPaidDialog
        entry={payOpen} onClose={() => setPayOpen(null)} onConfirm={confirmPay}
      />
    </div>
  );
}
