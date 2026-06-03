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
import { Plus, Send, Trash2 } from "lucide-react";

const TRIGGERS = [
  ["notify_out_of_stock", "Item Out of Stock → instant alert"],
  ["notify_low_stock", "Item Low Stock → instant alert"],
  ["notify_large_purchase", "Large Purchase above threshold → alert"],
  ["notify_morning_report", "Daily Morning Stock Summary (8 AM IST)"],
  ["notify_daily_report", "Daily Sales + Expense Report (10 PM IST)"],
  ["notify_no_sales_reminder", "No Sales Reminder (11 PM IST)"],
  ["notify_daily_loss", "Daily Net Loss → instant alert"],
];

function statusBadge(status) {
  const cls = status === "sent" ? "bg-green-100 text-green-700" :
    status === "failed" ? "bg-red-100 text-red-700" :
    status === "log_only" ? "bg-slate-100 text-slate-700" :
    "bg-amber-100 text-amber-700";
  return <span className={`text-xs px-2 py-0.5 rounded-full ${cls}`}>{status}</span>;
}

function NumberDialog({ open, onOpenChange, onSaved }) {
  const [form, setForm] = useState({ name: "", phone: "", is_active: true });
  const save = async () => {
    if (!form.name.trim() || !form.phone.trim()) return toast.error("Name and phone required");
    try {
      await api.post("/whatsapp/numbers", form);
      setForm({ name: "", phone: "", is_active: true });
      onOpenChange(false);
      onSaved();
      toast.success("Number added");
    } catch (err) { toast.error(formatApiError(err)); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl">
        <DialogHeader><DialogTitle className="font-display">Add WhatsApp Number</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label>Name</Label><Input data-testid="new-wa-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-11" placeholder="e.g. Jaya Sai" /></div>
          <div>
            <Label>Phone (with country code, no +)</Label>
            <Input data-testid="new-wa-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="h-11 tabular-nums" placeholder="e.g. 919876543210" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="rounded-full">Cancel</Button>
          <Button onClick={save} data-testid="new-wa-save" className="rounded-full bg-orange-600 hover:bg-orange-700">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function NumbersCard({ nums, onChange }) {
  const [openNew, setOpenNew] = useState(false);

  const testNum = async (n) => {
    try {
      const { data } = await api.post("/whatsapp/test", { number_id: n.id });
      if (data.log_only) toast.info("Logged (no WhatsApp credentials yet — set env vars to send real messages)");
      else if (data.status === "sent") toast.success("Test message sent");
      else toast.error(`Status: ${data.status}`);
      onChange();
    } catch (err) { toast.error(formatApiError(err)); }
  };
  const toggleNum = async (n) => {
    try { await api.patch(`/whatsapp/numbers/${n.id}`, { is_active: !n.is_active }); onChange(); }
    catch (err) { toast.error(formatApiError(err)); }
  };
  const delNum = async (n) => {
    if (!window.confirm(`Remove ${n.name} (${n.phone})?`)) return;
    try { await api.delete(`/whatsapp/numbers/${n.id}`); onChange(); toast.success("Removed"); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm">
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display text-base font-semibold text-slate-900">Recipient Numbers</h3>
          <Button onClick={() => setOpenNew(true)} data-testid="wa-add-number" size="sm" className="rounded-full bg-orange-600 hover:bg-orange-700">
            <Plus size={14} className="mr-1" />Add Number
          </Button>
        </div>
        {nums.length === 0 ? (
          <p className="text-sm text-slate-500 py-4">No numbers added. Add admin/staff WhatsApp numbers to receive alerts.</p>
        ) : (
          <Table>
            <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Phone</TableHead><TableHead>Active</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
            <TableBody>
              {nums.map((n) => (
                <TableRow key={n.id} data-testid={`wa-num-row-${n.id}`}>
                  <TableCell className="font-medium">{n.name}</TableCell>
                  <TableCell className="tabular-nums">+{n.phone}</TableCell>
                  <TableCell><Switch checked={n.is_active} onCheckedChange={() => toggleNum(n)} data-testid={`wa-num-toggle-${n.id}`} /></TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="ghost" onClick={() => testNum(n)} data-testid={`wa-num-test-${n.id}`}><Send size={14} className="mr-1" />Test</Button>
                    <Button size="sm" variant="ghost" onClick={() => delNum(n)} className="text-red-600" data-testid={`wa-num-del-${n.id}`}><Trash2 size={14} /></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <NumberDialog open={openNew} onOpenChange={setOpenNew} onSaved={onChange} />
      </CardContent>
    </Card>
  );
}

function TriggersCard({ settings, onChange }) {
  const saveSettings = async (patch) => {
    try { await api.patch("/whatsapp/settings", patch); onChange(); }
    catch (err) { toast.error(formatApiError(err)); }
  };
  const runJob = async (job) => {
    try { await api.post(`/whatsapp/run-job/${job}`); toast.success("Job executed"); onChange(); }
    catch (err) { toast.error(formatApiError(err)); }
  };
  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm">
      <CardContent className="p-5">
        <h3 className="font-display text-base font-semibold text-slate-900 mb-3">Triggers</h3>
        <div className="space-y-2">
          {TRIGGERS.map(([k, label]) => (
            <div key={k} className="flex items-center justify-between p-3 rounded-xl bg-orange-50/40 border border-orange-100">
              <Label className="text-sm">{label}</Label>
              <Switch checked={!!settings[k]} onCheckedChange={(v) => saveSettings({ [k]: v })} data-testid={`wa-trigger-${k}`} />
            </div>
          ))}
          <div className="flex items-center justify-between p-3 rounded-xl bg-orange-50/40 border border-orange-100">
            <Label className="text-sm">Large Purchase Threshold (₹)</Label>
            <Input type="number" min="0" step="100" defaultValue={settings.large_purchase_threshold}
              onBlur={(e) => saveSettings({ large_purchase_threshold: parseFloat(e.target.value) })}
              data-testid="wa-threshold-input" className="h-9 w-32 tabular-nums text-right" />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => runJob("morning_report")} data-testid="wa-run-morning" className="rounded-full">Run Morning Now</Button>
          <Button size="sm" variant="outline" onClick={() => runJob("daily_report")} data-testid="wa-run-daily" className="rounded-full">Run Daily Now</Button>
          <Button size="sm" variant="outline" onClick={() => runJob("no_sales_reminder")} data-testid="wa-run-reminder" className="rounded-full">Run Reminder Now</Button>
        </div>
      </CardContent>
    </Card>
  );
}

function LogCard({ log, onChange }) {
  const retry = async (id) => {
    try { await api.post(`/whatsapp/retry/${id}`); toast.success("Retry queued"); onChange(); }
    catch (err) { toast.error(formatApiError(err)); }
  };
  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm">
      <CardContent className="p-5">
        <h3 className="font-display text-base font-semibold text-slate-900 mb-3">Recent Notifications</h3>
        {log.length === 0 ? <p className="text-sm text-slate-500 py-4">No notifications yet.</p> : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Type</TableHead><TableHead>To</TableHead><TableHead>Status</TableHead><TableHead></TableHead></TableRow></TableHeader>
              <TableBody>
                {log.map((l) => (
                  <TableRow key={l.id} data-testid={`wa-log-${l.id}`}>
                    <TableCell className="text-xs text-slate-500 tabular-nums">{new Date(l.created_at).toLocaleString()}</TableCell>
                    <TableCell className="text-xs">{l.type}</TableCell>
                    <TableCell className="text-xs tabular-nums">+{l.to}</TableCell>
                    <TableCell>{statusBadge(l.status)}</TableCell>
                    <TableCell>
                      {l.status === "failed" && (
                        <Button size="sm" variant="ghost" onClick={() => retry(l.id)} data-testid={`wa-retry-${l.id}`} className="text-orange-700">Retry</Button>
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
  );
}

export default function WhatsAppPane() {
  const [nums, setNums] = useState([]);
  const [settings, setSettings] = useState(null);
  const [log, setLog] = useState([]);

  const loadAll = useCallback(async () => {
    try {
      const [n, s, l] = await Promise.all([
        api.get("/whatsapp/numbers"),
        api.get("/whatsapp/settings"),
        api.get("/whatsapp/log", { params: { limit: 20 } }),
      ]);
      setNums(n.data);
      setSettings(s.data);
      setLog(l.data);
    } catch (err) { console.error("Failed to load WhatsApp settings:", err); }
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);

  if (!settings) return null;

  return (
    <div className="space-y-4 mt-4">
      <NumbersCard nums={nums} onChange={loadAll} />
      <TriggersCard settings={settings} onChange={loadAll} />
      <LogCard log={log} onChange={loadAll} />
    </div>
  );
}
