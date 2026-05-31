import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Save, KeyRound, Send, Trash2 } from "lucide-react";

export default function Settings() {
  return (
    <div className="space-y-6 animate-fade-up" data-testid="settings-page">
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Admin</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-600 text-sm mt-1">Everything you might need to change — no developer needed.</p>
      </div>

      <Tabs defaultValue="business" className="w-full">
        <TabsList className="bg-orange-50 p-1 rounded-full overflow-x-auto flex w-full max-w-full">
          <TabsTrigger value="business" data-testid="settings-tab-business" className="rounded-full">Business</TabsTrigger>
          <TabsTrigger value="categories" data-testid="settings-tab-categories" className="rounded-full">Categories</TabsTrigger>
          <TabsTrigger value="expense-cats" data-testid="settings-tab-expense-cats" className="rounded-full">Expense Cats</TabsTrigger>
          <TabsTrigger value="units" data-testid="settings-tab-units" className="rounded-full">Units</TabsTrigger>
          <TabsTrigger value="users" data-testid="settings-tab-users" className="rounded-full">Users</TabsTrigger>
          <TabsTrigger value="staff" data-testid="settings-tab-staff" className="rounded-full">Payroll Staff</TabsTrigger>
          <TabsTrigger value="whatsapp" data-testid="settings-tab-whatsapp" className="rounded-full">WhatsApp</TabsTrigger>
          <TabsTrigger value="reorder" data-testid="settings-tab-reorder" className="rounded-full">Reorder Levels</TabsTrigger>
        </TabsList>

        <TabsContent value="business"><BusinessProfilePane /></TabsContent>
        <TabsContent value="categories"><NamedListPane apiPath="/categories" label="Category" testid="categories" /></TabsContent>
        <TabsContent value="expense-cats"><NamedListPane apiPath="/expense-categories" label="Expense Category" testid="expense-cats" /></TabsContent>
        <TabsContent value="units"><NamedListPane apiPath="/units" label="Unit" testid="units" /></TabsContent>
        <TabsContent value="users"><UsersPane /></TabsContent>
        <TabsContent value="staff"><StaffPane /></TabsContent>
        <TabsContent value="whatsapp"><WhatsAppPane /></TabsContent>
        <TabsContent value="reorder"><ReorderPane /></TabsContent>
      </Tabs>
    </div>
  );
}

function BusinessProfilePane() {
  const [p, setP] = useState({ name: "", address: "", phone: "", logo_base64: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.get("/business-profile").then(({ data }) => data && setP(data)); }, []);

  const handleLogo = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 500_000) return toast.error("Logo too large (max 500KB)");
    const reader = new FileReader();
    reader.onload = (ev) => setP({ ...p, logo_base64: ev.target.result });
    reader.readAsDataURL(file);
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.patch("/business-profile", p);
      toast.success("Business profile saved");
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  };

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm mt-4">
      <CardContent className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label className="text-sm mb-1 block">Dhaba Name</Label>
          <Input data-testid="biz-name-input" value={p.name || ""} onChange={(e) => setP({ ...p, name: e.target.value })} className="h-11" />
        </div>
        <div>
          <Label className="text-sm mb-1 block">Phone</Label>
          <Input data-testid="biz-phone-input" value={p.phone || ""} onChange={(e) => setP({ ...p, phone: e.target.value })} className="h-11" />
        </div>
        <div className="md:col-span-2">
          <Label className="text-sm mb-1 block">Address</Label>
          <Input data-testid="biz-address-input" value={p.address || ""} onChange={(e) => setP({ ...p, address: e.target.value })} className="h-11" />
        </div>
        <div className="md:col-span-2">
          <Label className="text-sm mb-1 block">Logo</Label>
          <div className="flex items-center gap-4">
            {p.logo_base64 ? <img src={p.logo_base64} alt="logo" className="h-16 w-16 rounded-xl object-cover border" /> :
              <div className="h-16 w-16 rounded-xl bg-orange-100 text-orange-700 flex items-center justify-center font-display font-bold">SP</div>}
            <Input type="file" accept="image/*" data-testid="biz-logo-input" onChange={handleLogo} className="h-11" />
          </div>
        </div>
        <div className="md:col-span-2">
          <Button onClick={save} disabled={saving} data-testid="biz-save-button" className="rounded-full bg-orange-600 hover:bg-orange-700">
            <Save size={16} className="mr-1" />{saving ? "Saving..." : "Save Profile"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function NamedListPane({ apiPath, label, testid }) {
  const [rows, setRows] = useState([]);
  const [name, setName] = useState("");

  const load = () => { api.get(apiPath, { params: { include_inactive: true } }).then(({ data }) => setRows(data)); };
  useEffect(() => { load(); }, [apiPath]);

  const add = async () => {
    if (!name.trim()) return;
    try { await api.post(apiPath, { name: name.trim() }); setName(""); load(); toast.success(`${label} added`); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const toggle = async (row) => {
    try { await api.patch(`${apiPath}/${row.id}`, { is_active: !row.is_active }); load(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm mt-4">
      <CardContent className="p-5">
        <div className="flex gap-2 mb-4">
          <Input data-testid={`${testid}-new-name`} value={name} onChange={(e) => setName(e.target.value)}
            placeholder={`New ${label.toLowerCase()} name`} className="h-11 max-w-sm" />
          <Button onClick={add} data-testid={`${testid}-add-btn`} className="rounded-full bg-orange-600 hover:bg-orange-700"><Plus size={16} /></Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow><TableHead>Name</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Action</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id} data-testid={`${testid}-row-${r.id}`}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell>{r.is_active ? <span className="text-green-700 text-xs font-semibold">Active</span> : <span className="text-slate-400 text-xs">Inactive</span>}</TableCell>
                <TableCell className="text-right">
                  <Switch checked={r.is_active} onCheckedChange={() => toggle(r)} data-testid={`${testid}-toggle-${r.id}`} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function UsersPane() {
  const [users, setUsers] = useState([]);
  const [openNew, setOpenNew] = useState(false);
  const [openReset, setOpenReset] = useState(null);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "staff" });
  const [resetPwd, setResetPwd] = useState("");

  const load = () => { api.get("/users").then(({ data }) => setUsers(data)); };
  useEffect(() => { load(); }, []);

  const create = async () => {
    try { await api.post("/users", form); setOpenNew(false); setForm({ name: "", email: "", password: "", role: "staff" }); load(); toast.success("User added"); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const changeRole = async (u, role) => {
    try { await api.patch(`/users/${u.id}`, { role }); load(); toast.success("Role updated"); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const toggleActive = async (u) => {
    try { await api.patch(`/users/${u.id}`, { is_active: !u.is_active }); load(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const reset = async () => {
    try { await api.post(`/users/${openReset.id}/reset-password`, { new_password: resetPwd });
      setOpenReset(null); setResetPwd(""); toast.success("Password reset"); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  return (
    <Card className="rounded-2xl border-orange-900/10 shadow-sm mt-4">
      <CardContent className="p-5">
        <div className="flex justify-end mb-3">
          <Button onClick={() => setOpenNew(true)} data-testid="user-add-btn" className="rounded-full bg-orange-600 hover:bg-orange-700"><Plus size={16} className="mr-1" />Add User</Button>
        </div>
        <Table>
          <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Role</TableHead><TableHead>Active</TableHead><TableHead></TableHead></TableRow></TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id} data-testid={`user-row-${u.id}`}>
                <TableCell className="font-medium">{u.name}</TableCell>
                <TableCell className="text-slate-600">{u.email}</TableCell>
                <TableCell>
                  <Select value={u.role} onValueChange={(v) => changeRole(u, v)}>
                    <SelectTrigger className="h-9 w-32"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">admin</SelectItem>
                      <SelectItem value="staff">staff</SelectItem>
                      <SelectItem value="viewer">viewer</SelectItem>
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell><Switch checked={u.is_active} onCheckedChange={() => toggleActive(u)} data-testid={`user-toggle-${u.id}`} /></TableCell>
                <TableCell>
                  <Button size="sm" variant="ghost" onClick={() => setOpenReset(u)} data-testid={`user-reset-${u.id}`}><KeyRound size={14} /></Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <Dialog open={openNew} onOpenChange={setOpenNew}>
          <DialogContent className="rounded-2xl">
            <DialogHeader><DialogTitle className="font-display">Add User</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>Name</Label><Input data-testid="new-user-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-11" /></div>
              <div><Label>Email</Label><Input type="email" data-testid="new-user-email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="h-11" /></div>
              <div><Label>Password</Label><Input type="text" data-testid="new-user-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="h-11" /></div>
              <div><Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="new-user-role" className="h-11"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">admin</SelectItem>
                    <SelectItem value="staff">staff</SelectItem>
                    <SelectItem value="viewer">viewer</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpenNew(false)} className="rounded-full">Cancel</Button>
              <Button onClick={create} data-testid="new-user-save" className="rounded-full bg-orange-600 hover:bg-orange-700">Save</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={!!openReset} onOpenChange={(o) => !o && setOpenReset(null)}>
          <DialogContent className="rounded-2xl">
            <DialogHeader><DialogTitle className="font-display">Reset password for {openReset?.name}</DialogTitle></DialogHeader>
            <Input type="text" data-testid="reset-new-pwd" value={resetPwd} onChange={(e) => setResetPwd(e.target.value)} placeholder="New password" className="h-11" />
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpenReset(null)} className="rounded-full">Cancel</Button>
              <Button onClick={reset} data-testid="reset-confirm" className="rounded-full bg-orange-600 hover:bg-orange-700">Reset</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

function ReorderPane() {
  const [items, setItems] = useState([]);
  const [edits, setEdits] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.get("/items").then(({ data }) => setItems(data.filter((i) => i.is_active))); }, []);

  const save = async () => {
    const updates = Object.entries(edits).map(([item_id, reorder_level]) => ({ item_id, reorder_level: parseFloat(reorder_level) }));
    if (updates.length === 0) return toast.info("No changes to save");
    setSaving(true);
    try { await api.post("/items/bulk-reorder", { updates }); toast.success(`${updates.length} items updated`); setEdits({});
      api.get("/items").then(({ data }) => setItems(data.filter((i) => i.is_active))); }
    catch (err) { toast.error(formatApiError(err)); }
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
          <TableHeader><TableRow><TableHead>Item</TableHead><TableHead>Category</TableHead><TableHead>Unit</TableHead><TableHead className="text-right">Reorder Level</TableHead></TableRow></TableHeader>
          <TableBody>
            {items.map((it) => (
              <TableRow key={it.id} data-testid={`reorder-row-${it.id}`}>
                <TableCell className="font-medium">{it.name}</TableCell>
                <TableCell className="text-slate-600">{it.category}</TableCell>
                <TableCell className="text-slate-600">{it.unit}</TableCell>
                <TableCell className="text-right">
                  <Input type="number" min="0" step="0.01" data-testid={`reorder-input-${it.id}`}
                    defaultValue={it.reorder_level}
                    onChange={(e) => setEdits({ ...edits, [it.id]: e.target.value })}
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

function StaffPane() {
  const [rows, setRows] = useState([]);
  const [openNew, setOpenNew] = useState(false);
  const [form, setForm] = useState({ name: "", default_salary: "0", phone: "" });

  const load = () => api.get("/staff").then(({ data }) => setRows(data));
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.name.trim()) return toast.error("Name required");
    try {
      await api.post("/staff", { name: form.name.trim(), default_salary: parseFloat(form.default_salary || 0), phone: form.phone || "" });
      setOpenNew(false); setForm({ name: "", default_salary: "0", phone: "" }); load();
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

function WhatsAppPane() {
  const [nums, setNums] = useState([]);
  const [settings, setSettings] = useState(null);
  const [log, setLog] = useState([]);
  const [openNew, setOpenNew] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", is_active: true });

  const loadAll = () => {
    api.get("/whatsapp/numbers").then(({ data }) => setNums(data));
    api.get("/whatsapp/settings").then(({ data }) => setSettings(data));
    api.get("/whatsapp/log", { params: { limit: 20 } }).then(({ data }) => setLog(data));
  };
  useEffect(() => { loadAll(); }, []);

  const saveSettings = async (patch) => {
    try {
      const { data } = await api.patch("/whatsapp/settings", patch);
      setSettings(data);
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const addNum = async () => {
    if (!form.name.trim() || !form.phone.trim()) return toast.error("Name and phone required");
    try {
      await api.post("/whatsapp/numbers", form);
      setOpenNew(false); setForm({ name: "", phone: "", is_active: true }); loadAll();
      toast.success("Number added");
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const toggleNum = async (n) => {
    try { await api.patch(`/whatsapp/numbers/${n.id}`, { is_active: !n.is_active }); loadAll(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const delNum = async (n) => {
    if (!window.confirm(`Remove ${n.name} (${n.phone})?`)) return;
    try { await api.delete(`/whatsapp/numbers/${n.id}`); loadAll(); toast.success("Removed"); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const testNum = async (n) => {
    try {
      const { data } = await api.post("/whatsapp/test", { number_id: n.id });
      if (data.log_only) toast.info("Logged (no WhatsApp credentials yet — set env vars to send real messages)");
      else if (data.status === "sent") toast.success("Test message sent");
      else toast.error(`Status: ${data.status}`);
      loadAll();
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const runJob = async (job) => {
    try { await api.post(`/whatsapp/run-job/${job}`); toast.success("Job executed"); loadAll(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const retry = async (id) => {
    try { await api.post(`/whatsapp/retry/${id}`); toast.success("Retry queued"); loadAll(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  if (!settings) return null;

  return (
    <div className="space-y-4 mt-4">
      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display text-base font-semibold text-slate-900">Recipient Numbers</h3>
            <Button onClick={() => setOpenNew(true)} data-testid="wa-add-number" size="sm" className="rounded-full bg-orange-600 hover:bg-orange-700">
              <Plus size={14} className="mr-1" />Add Number
            </Button>
          </div>
          {nums.length === 0 ? <p className="text-sm text-slate-500 py-4">No numbers added. Add admin/staff WhatsApp numbers to receive alerts.</p> : (
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
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-orange-900/10 shadow-sm">
        <CardContent className="p-5">
          <h3 className="font-display text-base font-semibold text-slate-900 mb-3">Triggers</h3>
          <div className="space-y-2">
            {[
              ["notify_out_of_stock", "Item Out of Stock → instant alert"],
              ["notify_low_stock", "Item Low Stock → instant alert"],
              ["notify_large_purchase", "Large Purchase above threshold → alert"],
              ["notify_morning_report", "Daily Morning Stock Summary (8 AM IST)"],
              ["notify_daily_report", "Daily Sales + Expense Report (10 PM IST)"],
              ["notify_no_sales_reminder", "No Sales Reminder (11 PM IST)"],
              ["notify_daily_loss", "Daily Net Loss → instant alert"],
            ].map(([k, label]) => (
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
                      <TableCell>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          l.status === "sent" ? "bg-green-100 text-green-700" :
                          l.status === "failed" ? "bg-red-100 text-red-700" :
                          l.status === "log_only" ? "bg-slate-100 text-slate-700" :
                          "bg-amber-100 text-amber-700"}`}>{l.status}</span>
                      </TableCell>
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

      <Dialog open={openNew} onOpenChange={setOpenNew}>
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
            <Button variant="outline" onClick={() => setOpenNew(false)} className="rounded-full">Cancel</Button>
            <Button onClick={addNum} data-testid="new-wa-save" className="rounded-full bg-orange-600 hover:bg-orange-700">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

