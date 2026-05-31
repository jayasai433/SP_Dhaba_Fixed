import { useState } from "react";

/**
 * useDateFilter — encapsulates the [start, setStart] + [end, setEnd] date
 * range filter pattern repeated across Purchases and Expenses.
 *
 * @returns {{ start, end, setStart, setEnd, dateParams, clearDates }}
 *   start       — ISO date string for "from" filter (YYYY-MM-DD or "")
 *   end         — ISO date string for "to" filter (YYYY-MM-DD or "")
 *   setStart    — setter for start
 *   setEnd      — setter for end
 *   dateParams  — { start, end } object with only non-empty values, ready to
 *                 spread into an API query params object
 *   clearDates  — resets both to empty string
 *
 * Usage:
 *   const { start, end, setStart, setEnd, dateParams } = useDateFilter();
 *   // In useCallback:
 *   api.get("/purchases", { params: { ...dateParams, item_id: filterItem } });
 *   // In JSX:
 *   <Input value={start} onChange={(e) => setStart(e.target.value)} />
 *   <Input value={end}   onChange={(e) => setEnd(e.target.value)} />
 */
export function useDateFilter() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const dateParams = {
    ...(start ? { start } : {}),
    ...(end   ? { end }   : {}),
  };

  const clearDates = () => { setStart(""); setEnd(""); };

  return { start, end, setStart, setEnd, dateParams, clearDates };
}
