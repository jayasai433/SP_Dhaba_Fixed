import { useState } from "react";
import { Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

/**
 * VoidDialog
 * Replaces window.prompt() for void confirmations across Purchases,
 * Daily Usage, and Expenses pages. Collects a mandatory reason string
 * before allowing the void to proceed.
 *
 * Props:
 *   open      . boolean, controls visibility
 *   onConfirm . (reason: string) => void, called with trimmed reason text
 *   onCancel  . () => void
 *   entryLabel. optional descriptor shown in the dialog (e.g. "purchase")
 */
export default function VoidDialog({ open, onConfirm, onCancel, entryLabel = "entry" }) {
  const [reason, setReason] = useState("");
  const [error, setError]   = useState("");

  if (!open) return null;

  const handleConfirm = () => {
    const trimmed = reason.trim();
    if (trimmed.length < 3) {
      setError("Please enter a reason (at least 3 characters).");
      return;
    }
    setReason("");
    setError("");
    onConfirm(trimmed);
  };

  const handleCancel = () => {
    setReason("");
    setError("");
    onCancel();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      data-testid="void-dialog"
    >
      <div className="bg-white rounded-2xl shadow-xl border border-red-200 p-6 w-full max-w-sm mx-4 animate-fade-up">
        <div className="flex items-start gap-3 mb-4">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
            <Ban size={20} className="text-red-600" />
          </div>
          <div>
            <h3 className="font-display font-semibold text-slate-900 text-base">
              Void this {entryLabel}?
            </h3>
            <p className="text-sm text-slate-500 mt-1">
              This action cannot be undone. Please provide a reason for voiding.
            </p>
          </div>
        </div>

        <div className="mb-4">
          <Label className="text-sm font-medium text-slate-700 mb-1.5 block">
            Reason <span className="text-red-500">*</span>
          </Label>
          <Textarea
            data-testid="void-reason-input"
            value={reason}
            onChange={(e) => { setReason(e.target.value); setError(""); }}
            placeholder="e.g. Entered wrong item, duplicate entry..."
            rows={3}
            className="bg-white resize-none"
            autoFocus
          />
          {error && (
            <p className="text-xs text-red-600 mt-1" data-testid="void-reason-error">{error}</p>
          )}
        </div>

        <div className="flex gap-2 justify-end">
          <Button
            variant="outline"
            onClick={handleCancel}
            className="rounded-full border-slate-200 text-slate-600 hover:bg-slate-50"
            data-testid="void-cancel-btn"
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            className="rounded-full bg-red-600 hover:bg-red-700 text-white"
            data-testid="void-confirm-btn"
          >
            Void entry
          </Button>
        </div>
      </div>
    </div>
  );
}
