import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { inr, todayIST } from "@/lib/format";

export default function MarkPaidDialog({ entry, onClose, onConfirm }) {
  const [paidDate, setPaidDate] = useState(todayIST());
  useEffect(() => { if (entry) setPaidDate(todayIST()); }, [entry]);

  return (
    <Dialog open={!!entry} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="rounded-2xl">
        <DialogHeader><DialogTitle className="font-display">Mark as Paid — {entry?.staff_name}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>Paid Date</Label>
            <Input type="date" data-testid="salary-paid-date" value={paidDate} onChange={(e) => setPaidDate(e.target.value)} className="h-11" />
          </div>
          <div className="text-sm text-slate-600">
            Net payable: <b className="tabular-nums">{inr(entry?.net_payable || 0)}</b>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="rounded-full">Cancel</Button>
          <Button onClick={() => onConfirm(paidDate)} data-testid="salary-pay-confirm" className="rounded-full bg-green-600 hover:bg-green-700">Confirm Paid</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
