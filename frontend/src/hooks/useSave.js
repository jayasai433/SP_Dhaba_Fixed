import { useState } from "react";
import { toast } from "sonner";
import { formatApiError } from "@/lib/api";

/**
 * useSave — encapsulates the saving/setSaving/try/catch/finally pattern
 * repeated across Purchases, Sales, Expenses, DailyUsage.
 *
 * @param {Function} apiCall  — async fn that performs the API call
 * @param {Object}   options
 *   @param {string}   options.successMessage — toast shown on success
 *   @param {Function} options.onSuccess      — called after successful save
 *
 * @returns {{ save, saving }}
 *   save(payload?)  — call this from your form's onSubmit (after validation)
 *   saving          — boolean, true while the API call is in-flight
 *
 * Usage:
 *   const { save, saving } = useSave(
 *     (data) => api.post("/purchases", data),
 *     { successMessage: "Purchase saved", onSuccess: () => { load(); reset(); } }
 *   );
 */
export function useSave(apiCall, { successMessage = "Saved", onSuccess } = {}) {
  const [saving, setSaving] = useState(false);

  const save = async (payload) => {
    setSaving(true);
    try {
      await apiCall(payload);
      toast.success(successMessage);
      onSuccess?.();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  return { save, saving };
}
