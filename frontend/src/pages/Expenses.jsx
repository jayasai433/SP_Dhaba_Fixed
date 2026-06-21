import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { inr, fmtDate, fmtTimestamp } from "@/lib/format";
import { Plus, Wallet, Ban } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { SKELETON_KEYS } from "@/lib/skeletons";
import DuplicateWarningDialog from "@/components/DuplicateWarningDialog";
import VoidDialog from "@/components/VoidDialog";
import { useExpenses } from "@/hooks/useExpenses";

// ── Mini summary card ─────────────────────────────────────────────────────────
function SummaryCard({ label, value, testid, highlight }) {
  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm" data-testid={testid}>
      <CardContent className="p-4">
        <div className="text-xs uppercase tracking-wider text-slate-500">{label}</div>
        <div className={`font-display font-bold text-2xl tabular-nums ${highlight ? "text-orange-700" : "text-slate-900"}`}>
          {inr(value)}
        </div>
      </CardContent>
    </Card>
  );
}

export default function Expenses() {
  const { user } = useAuth();
  const canAdd = ["admin", "staff"].includes(user.role);

  const {
    cats, rows, filterCat, setFilterCat,
    start, end, setStart, setEnd,
    date, setDate, cat, setCat, desc, setDesc, amt, setAmt,
    dayTotal, weekTotal, monthTotal,
    validateAndSave, saving,
    dupDialog, confirmDuplicate, cancelDuplicate,
    voidDialogId, setVoidDialogId, handleVoidConfirm,
  } = useExpenses();

  return (
    <div className="space-y-6 animate-fade-up" data-testid="expenses-page">
      <DuplicateWarningDialog
        open={dupDialog} onConfirm={confirmDuplicate} onCancel={cancelDuplicate}
        message="An expense with the same category and amount was just recorded seconds ago. Did you intend to enter this again?"
      />
      <VoidDialog
        open={!!voidDialogId} onConfirm={handleVoidConfirm}
        onCancel={() => setVoidDialogId(null)} entryLabel="expense"
      />

      {/* Header */}
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Operating Expenses</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Expenses</h1>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <SummaryCard label="Today"      value={dayTotal}   testid="exp-today-card" />
        <SummaryCard label="This Week"  value={weekTotal}  testid="exp-week-card" />
        <SummaryCard label="This Month" value={monthTotal} testid="exp-month-card" highlight
          extraClass="col-span-2 md:col-span-1" />
      </div>

      {/* Add Expense Form */}
      {canAdd && (
        <Card className="rounded-2xl border-orange-900/10 shadow-sm">
          <CardContent className="p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Plus size={18} className="text-orange-600" />Add Expense
            </h3>
            <form onSubmit={validateAndSave} className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">Date</Label>
                <Input type="date" data-testid="exp-date-input" value={date}
                  onChange={(e) => setDate(e.target.value)} className="h-11 bg-white" />
              </div>
              <div className="md:col-span-3">
                <Label className="text-sm mb-1.5 block">Category</Label>
                <Select value={cat} onValueChange={setCat}>
                  <SelectTrigger data-testid="exp-cat-select" className="h-11 bg-white">
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    {cats.map((c) => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-5">
                <Label className="text-sm mb-1.5 block">Description</Label>
                <Input data-testid="exp-desc-input" value={desc}
                  onChange={(e) => setDesc(e.target.value)} className="h-11 bg-white" placeholder="Optional" />
              </div>
              <div className="md:col-span-2">
                <Label className="text-sm mb-1.5 block">Amount (₹)</Label>
                <Input type="number" step="0.01" min="0" data-testid="exp-amount-input" value={amt}
                  onChange={(e) => setAmt(e.target.value)} className="h-11 bg-white tabular-nums" placeholder="0" />
              </div>
              <div className="md:col-span-12">
                <Button type="submit" disabled={saving} data-testid="exp-submit-button"
                  className="rounded-full bg-orange-600 hover:bg-orange-700 px-6 active:scale-95">
                  {saving ? "Saving..." : "Save Expense"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Expense History Table */}
      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <div className="flex flex-col md:flex-row md:items-end gap-3 mb-4">
            <div className="flex-1">
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">Filter Category</Label>
              <Select value={filterCat} onValueChange={setFilterCat}>
                <SelectTrigger data-testid="exp-filter-cat" className="h-10 bg-white"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {cats.map((c) => <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">From</Label>
              <Input type="date" data-testid="exp-filter-start" value={start}
                onChange={(e) => setStart(e.target.value)} className="h-10 bg-white" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-slate-500 mb-1 block">To</Label>
              <Input type="date" data-testid="exp-filter-end" value={end}
                onChange={(e) => setEnd(e.target.value)} className="h-10 bg-white" />
            </div>
          </div>

          {rows === null ? (
            <div className="space-y-2">
              {SKELETON_KEYS.slice(0, 5).map((k) => <Skeleton key={k} className="h-10 rounded-lg" />)}
            </div>
          ) : rows.length === 0 ? (
            <div className="text-center py-10 text-slate-500" data-testid="expenses-empty-state">
              <Wallet className="mx-auto text-orange-300 mb-2" size={36} />
              <p className="font-medium">No expense records</p>
              <p className="text-sm mt-1">Log your first expense to start tracking operating cost.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead><TableHead>Category</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>By</TableHead><TableHead>Logged at</TableHead>
                    {canAdd && <TableHead></TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id} data-testid={`expense-row-${r.id}`}>
                      <TableCell className="tabular-nums">{fmtDate(r.date)}</TableCell>
                      <TableCell>{r.category}</TableCell>
                      <TableCell className="text-slate-500">{r.description || "—"}</TableCell>
                      <TableCell className="text-right tabular-nums font-semibold">{inr(r.amount)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{r.created_by_name}</TableCell>
                      <TableCell className="text-xs text-slate-400 tabular-nums whitespace-nowrap">
                        {fmtTimestamp(r.created_at)}
                      </TableCell>
                      {canAdd && (
                        <TableCell>
                          <button title="Void this entry" onClick={() => setVoidDialogId(r.id)}
                            className="text-red-400 hover:text-red-600 transition-colors"
                            data-testid={`void-expense-${r.id}`}>
                            <Ban size={15} />
                          </button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
