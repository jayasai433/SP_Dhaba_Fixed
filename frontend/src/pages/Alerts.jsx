import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sparkles, AlertCircle, PackageX, Plus } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { SKELETON_KEYS } from "@/lib/skeletons";

export default function Alerts() {
  const [alerts, setAlerts] = useState(null);

  useEffect(() => {
    const load = () => api.get("/alerts").then(({ data }) => setAlerts(data));
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  if (!alerts) {
    return <div className="space-y-3">{SKELETON_KEYS.slice(0, 4).map((k) => <Skeleton key={k} className="h-20 rounded-2xl" />)}</div>;
  }

  return (
    <div className="space-y-6 animate-fade-up" data-testid="alerts-page">
      <div>
        <div className="text-xs font-semibold tracking-widest uppercase text-orange-700">Inventory Alerts</div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Stock Alerts</h1>
        <p className="text-slate-600 text-sm mt-1">{alerts.length} item{alerts.length !== 1 ? "s" : ""} need your attention</p>
      </div>

      {alerts.length === 0 ? (
        <Card className="rounded-2xl border-green-200 bg-green-50/40" data-testid="no-alerts-celebration">
          <CardContent className="p-10 text-center">
            <Sparkles className="mx-auto text-green-600" size={48} />
            <h3 className="font-display text-2xl font-bold text-green-800 mt-3">All Good!</h3>
            <p className="text-green-700/80 mt-1">Every item is comfortably in stock. Great job keeping things stocked up!</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="alerts-list">
          {alerts.map((a) => {
            const isOut = a.status === "out";
            return (
              <Card key={a.item_id}
                data-testid={`alert-card-${a.item_id}`}
                className={`rounded-2xl border-2 ${isOut ? "border-red-300 bg-red-50/60" : "border-amber-300 bg-amber-50/60"}`}>
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    <div className={`h-11 w-11 rounded-xl flex items-center justify-center ${isOut ? "bg-red-600 text-white" : "bg-amber-500 text-white"}`}>
                      {isOut ? <PackageX size={22} /> : <AlertCircle size={22} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-display font-semibold text-slate-900 text-lg">{a.name}</h3>
                        <Badge className={isOut ? "bg-red-600 hover:bg-red-600" : "bg-amber-600 hover:bg-amber-600"}>
                          {isOut ? "Out of Stock" : "Low Stock"}
                        </Badge>
                      </div>
                      <div className="text-sm text-slate-600 mt-1">{a.category}</div>
                      <div className="text-sm mt-2 tabular-nums">
                        Available: <b>{a.qty_left} {a.unit}</b> · Reorder: <b>{a.reorder_level} {a.unit}</b>
                      </div>
                    </div>
                    <Link to={`/purchases?item=${a.item_id}`}>
                      <Button size="sm" data-testid={`log-purchase-${a.item_id}`}
                        className="rounded-full bg-orange-600 hover:bg-orange-700">
                        <Plus size={14} className="mr-1" />Log Purchase
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
