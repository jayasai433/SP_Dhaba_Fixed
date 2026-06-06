/**
 * StagingBanner — shown only in staging environment.
 * Prevents confusion between staging and production.
 * Controlled by REACT_APP_ENV environment variable.
 */
export default function StagingBanner() {
  if (process.env.REACT_APP_ENV !== "staging") return null;

  return (
    <div className="w-full bg-yellow-400 text-yellow-900 text-center text-xs font-semibold py-1.5 px-4 z-50">
      ⚠️ STAGING ENVIRONMENT — Data here is for testing only. Do not enter real transactions.
    </div>
  );
}
