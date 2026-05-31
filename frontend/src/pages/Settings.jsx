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
import { Plus, Save, KeyRound } from "lucide-react";

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
          <TabsTrigger value="units" data-testid="settings-tab-units" className="rounded-full">Units</TabsTrigger>
          <TabsTrigger value="users" data-testid="settings-tab-users" className="rounded-full">Users</TabsTrigger>
          <TabsTrigger value="reorder" data-testid="settings-tab-reorder" className="rounded-full">Reorder Levels</TabsTrigger>
        </TabsList>

        <TabsContent value="business"><BusinessProfilePane /></TabsContent>
        <TabsContent value="categories"><NamedListPane apiPath="/categories" label="Category" testid="categories" /></TabsContent>
        <TabsContent value="units"><NamedListPane apiPath="/units" label="Unit" testid="units" /></TabsContent>
        <TabsContent value="users"><UsersPane /></TabsContent>
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
