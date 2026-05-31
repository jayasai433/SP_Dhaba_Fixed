import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, KeyRound } from "lucide-react";

function AddUserDialog({ open, onOpenChange, onCreated }) {
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "staff" });
  const save = async () => {
    try {
      await api.post("/users", form);
      onCreated();
      setForm({ name: "", email: "", password: "", role: "staff" });
      onOpenChange(false);
      toast.success("User added");
    } catch (err) { toast.error(formatApiError(err)); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
          <Button variant="outline" onClick={() => onOpenChange(false)} className="rounded-full">Cancel</Button>
          <Button onClick={save} data-testid="new-user-save" className="rounded-full bg-orange-600 hover:bg-orange-700">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ResetPasswordDialog({ user, onClose, onDone }) {
  const [pwd, setPwd] = useState("");
  const reset = async () => {
    try {
      await api.post(`/users/${user.id}/reset-password`, { new_password: pwd });
      onDone(); setPwd(""); toast.success("Password reset");
    } catch (err) { toast.error(formatApiError(err)); }
  };
  return (
    <Dialog open={!!user} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="rounded-2xl">
        <DialogHeader><DialogTitle className="font-display">Reset password for {user?.name}</DialogTitle></DialogHeader>
        <Input type="text" data-testid="reset-new-pwd" value={pwd} onChange={(e) => setPwd(e.target.value)} placeholder="New password" className="h-11" />
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="rounded-full">Cancel</Button>
          <Button onClick={reset} data-testid="reset-confirm" className="rounded-full bg-orange-600 hover:bg-orange-700">Reset</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function UsersPane() {
  const [users, setUsers] = useState([]);
  const [openNew, setOpenNew] = useState(false);
  const [reset, setReset] = useState(null);

  const load = useCallback(async () => {
    const { data } = await api.get("/users");
    setUsers(data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const changeRole = async (u, role) => {
    try { await api.patch(`/users/${u.id}`, { role }); load(); toast.success("Role updated"); }
    catch (err) { toast.error(formatApiError(err)); }
  };
  const toggleActive = async (u) => {
    try { await api.patch(`/users/${u.id}`, { is_active: !u.is_active }); load(); }
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
                  <Button size="sm" variant="ghost" onClick={() => setReset(u)} data-testid={`user-reset-${u.id}`}><KeyRound size={14} /></Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <AddUserDialog open={openNew} onOpenChange={setOpenNew} onCreated={load} />
        <ResetPasswordDialog user={reset} onClose={() => setReset(null)} onDone={() => setReset(null)} />
      </CardContent>
    </Card>
  );
}
