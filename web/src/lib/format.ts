/**
 * Display formatting.
 *
 * Every function pins a locale and time zone. Left to the defaults, the server
 * would format in the container's locale and the client in the browser's, React
 * would see two different strings for the same data, and hydration would warn.
 */
const DATE = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : DATE.format(date);
}

const MONEY = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export function formatSalary(
  min: number | null | undefined,
  max: number | null | undefined,
): string {
  if (min && max) return `${MONEY.format(min)} – ${MONEY.format(max)}`;
  if (min) return `From ${MONEY.format(min)}`;
  if (max) return `Up to ${MONEY.format(max)}`;
  return "Not disclosed";
}

/** "full_time" and "REMOTE" both need to read as prose in a table cell. */
export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .replace(/[_-]+/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
