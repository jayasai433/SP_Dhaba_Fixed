// Currency, dates, helpers
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function inr(n) {
  const num = Number(n) || 0;
  return "₹" + num.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

// Format YYYY-MM-DD -> DD-MMM-YYYY
export function fmtDate(s) {
  if (!s) return ".";
  const [y, m, d] = s.split("T")[0].split("-");
  if (!y || !m || !d) return s;
  return `${d}-${MONTHS[parseInt(m, 10) - 1]}-${y}`;
}

// Format ISO timestamp → "31-May-2026 14:32 IST"
export function fmtTimestamp(iso) {
  if (!iso) return ".";
  const d = new Date(iso);
  const fmt = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
  return fmt.format(d) + " IST";
}

// Today in IST (Asia/Kolkata) as YYYY-MM-DD
export function todayIST() {
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric", month: "2-digit", day: "2-digit"
  });
  return fmt.format(new Date());
}
