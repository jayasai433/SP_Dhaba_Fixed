import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * DuplicateWarningDialog
 * Shown when a 409 duplicate-window error is returned from the backend.
 * Gives the user a clear choice: confirm it was intentional, or cancel.
 *
 * Props:
 *   open            — boolean, controls visibility
 *   onConfirm       — called when user says "Yes, save anyway"
 *   onCancel        — called when user says "No, cancel"
 *   message         — optional custom message (defaults to generic duplicate warning)
 */
export default function DuplicateWarningDialog({ open, onConfirm, onCancel, message }) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      data-testid="duplicate-warning-dialog"
    >
      <div className="bg-white rounded-2xl shadow-xl border border-orange-200 p-6 w-full max-w-sm mx-4 animate-fade-up">
        <div className="flex items-start gap-3 mb-4">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
            <AlertTriangle size={20} className="text-amber-600" />
          </div>
          <div>
            <h3 className="font-display font-semibold text-slate-900 text-base">
              Possible duplicate entry
            </h3>
            <p className="text-sm text-slate-500 mt-1">
              {message || "A similar entry was just recorded a few seconds ago. Did you mean to enter this again?"}
            </p>
          </div>
        </div>

        <div className="flex gap-2 justify-end mt-2">
          <Button
            variant="outline"
            onClick={onCancel}
            className="rounded-full border-slate-200 text-slate-600 hover:bg-slate-50"
            data-testid="dup-cancel-btn"
          >
            No, cancel
          </Button>
          <Button
            onClick={onConfirm}
            className="rounded-full bg-orange-600 hover:bg-orange-700 text-white"
            data-testid="dup-confirm-btn"
          >
            Yes, save anyway
          </Button>
        </div>
      </div>
    </div>
  );
}
