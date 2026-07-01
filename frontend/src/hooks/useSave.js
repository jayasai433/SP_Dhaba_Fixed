import { useState } from "react";
import { toast } from "sonner";
import { formatApiError } from "@/lib/api";

/**
 * useSave. encapsulates the saving/setSaving/try/catch/finally pattern
 * repeated across Purchases, Sales, Expenses, DailyUsage.
 *
 * @param {Function} apiCall . async fn that performs the API call
 * @param {Object}   options
 *   @param {string}   options.successMessage. toast shown on success
 *   @param {Function} options.onSuccess     . called after successful save
 *
 * @returns {{ save, saving }}
 *   save(payload?) . call this from your form's onSubmit (after validation)
 *   saving         . boolean, true while the API call is in-flight
 *
 * Usage:
 *   const { save, saving } = useSave(
 *     (data) => api.post("/purchases", data),
 *     { successMessage: "Purchase saved", onSuccess: () => { load(); reset(); } }
 *   );
 */
export function useSave(apiCall, { successMessage = "Saved", onSuccess } = {}) {
  const [saving, setSaving] = useState(false);
  const [dupDialog, setDupDialog] = useState(false);
  const [pendingPayload, setPendingPayload] = useState(null);

  const _call = async (payload, force = false) => {
    setSaving(true);
    try {
      await apiCall(payload);
      toast.success(successMessage);
      onSuccess?.();
    } catch (err) {
      const status = err?.response?.status;
      const msg = formatApiError(err);
      if (status === 409 && !force && msg.toLowerCase().includes("duplicate")) {
        // Possible double-submit. show confirmation dialog
        setPendingPayload(payload);
        setDupDialog(true);
      } else {
        toast.error(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  const save = (payload) => _call(payload, false);

  const confirmDuplicate = () => {
    const payload = pendingPayload;
    setDupDialog(false);
    setPendingPayload(null);
    _call(payload, true);  // force=true skips the 409 popup
  };

  const cancelDuplicate = () => {
    setDupDialog(false);
    setPendingPayload(null);
  };

  return { save, saving, dupDialog, confirmDuplicate, cancelDuplicate };
}
