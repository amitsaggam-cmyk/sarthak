export function formatDateTime(value) {
  if (!value) return "Not available";

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function isToday(value) {
  if (!value) return false;

  const date = new Date(value);
  const today = new Date();

  return (
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate()
  );
}

export function parseDisplayDate(value) {
  const match = String(value || "").trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!match) return "";

  const [, day, month, year] = match;
  return `${year}-${month}-${day}`;
}

export function isValidDisplayDate(value) {
  if (!value) return true;

  const isoDate = parseDisplayDate(value);
  if (!isoDate) return false;

  const [year, month, day] = isoDate.split("-").map(Number);
  const date = new Date(year, month - 1, day);

  return (
    date.getFullYear() === year &&
    date.getMonth() === month - 1 &&
    date.getDate() === day
  );
}
