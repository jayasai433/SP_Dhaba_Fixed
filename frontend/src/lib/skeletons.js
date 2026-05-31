// Stable keys for static skeleton placeholders. Using a constant array avoids
// "array index as key" warnings while keeping the visual identical.
export const SKELETON_KEYS = Object.freeze(
  Array.from({ length: 24 }, (_, i) => `skeleton-row-${i}`)
);
