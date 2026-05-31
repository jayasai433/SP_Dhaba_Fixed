import { useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Save } from "lucide-react";
import { useBusinessProfile } from "@/contexts/BusinessProfileContext";

export default function BusinessProfilePane() {
  const [p, setP] = useState({ name: "", address: "", phone: "", logo_base64: "" });
  const [saving, setSaving] = useState(false);
  const { refresh } = useBusinessProfile();

  const load = useCallback(async () => {
    const { data } = await api.get("/business-profile");
    if (data) setP(data);
  }, []);
  useEffect(() => { load(); }, [load]);

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
      refresh(); // propagate dhaba name/logo to header & display mode instantly
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
            {p.logo_base64 ? (
              <img src={p.logo_base64} alt="logo" className="h-16 w-16 rounded-xl object-cover border" />
            ) : (
              <div className="h-16 w-16 rounded-xl bg-orange-100 text-orange-700 flex items-center justify-center font-display font-bold">SP</div>
            )}
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
