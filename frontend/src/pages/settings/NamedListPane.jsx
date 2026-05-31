import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { Plus } from "lucide-react";

export default function NamedListPane({ apiPath, label, testid }) {
  const [rows, setRows] = useState([]);
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    const { data } = await api.get(apiPath, { params: { include_inactive: true } });
    setRows(data);
  }, [apiPath]);
  useEffect(() => { load(); }, [load]);

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
