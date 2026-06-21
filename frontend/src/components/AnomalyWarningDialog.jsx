/**
 * AnomalyWarningDialog
 * Shows Z-Score based anomaly warnings before saving.
 * User can still confirm and save — this is a warning, not a blocker.
 */
import { AlertTriangle, AlertOctagon } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export default function AnomalyWarningDialog({ open, warnings, severity, onConfirm, onCancel }) {
  const isCritical = severity === "critical";

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onCancel(); }}>
      <DialogContent className="rounded-2xl max-w-sm">
        <DialogHeader>
          <DialogTitle className={`flex items-center gap-2 ${isCritical ? "text-red-700" : "text-amber-700"}`}>
            {isCritical
              ? <AlertOctagon size={18} />
              : <AlertTriangle size={18} />
            }
            {isCritical ? "Critical Anomaly Detected" : "Unusual Entry Detected"}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          <div className={`border rounded-xl p-4 space-y-2 ${
            isCritical
              ? "bg-red-50 border-red-200"
              : "bg-amber-50 border-amber-200"
          }`}>
            {warnings.map((w, i) => (
              <p key={i} className={`text-sm ${isCritical ? "text-red-800" : "text-amber-800"}`}>
                {isCritical ? "🔴" : "⚠️"} {w}
              </p>
            ))}
          </div>

          <p className="text-sm text-slate-500">
            {isCritical
              ? "This entry is highly unusual. Please double-check before saving."
              : "This could be a genuine purchase — verify before saving."
            }
          </p>

          <div className="flex gap-3">
            <Button
              onClick={onCancel}
              variant="outline"
              className="flex-1 rounded-full"
            >
              Edit Entry
            </Button>
            <Button
              onClick={onConfirm}
              className={`flex-1 rounded-full ${
                isCritical
                  ? "bg-red-600 hover:bg-red-700"
                  : "bg-amber-600 hover:bg-amber-700"
              }`}
            >
              Save Anyway
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
