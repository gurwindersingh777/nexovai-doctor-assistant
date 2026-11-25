import type { DoctorSlot } from "@/types";

const TZ = "Asia/Kolkata";

export function parseDate(iso: string) {
  return new Date(/(Z|[+-]\d\d:?\d\d)$/i.test(iso) ? iso : `${iso}Z`);
}

const time = new Intl.DateTimeFormat("en-IN", {
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
  timeZone: TZ,
});
const weekday = new Intl.DateTimeFormat("en-IN", { weekday: "short", timeZone: TZ });
const dayNumber = new Intl.DateTimeFormat("en-IN", { day: "numeric", timeZone: TZ });
const month = new Intl.DateTimeFormat("en-IN", { month: "short", timeZone: TZ });
const dayKey = new Intl.DateTimeFormat("en-CA", { timeZone: TZ });

export const fmtTime = (iso: string) => time.format(parseDate(iso)).toUpperCase();
export const fmtWeekday = (iso: string) => weekday.format(parseDate(iso));
export const fmtDayNumber = (iso: string) => dayNumber.format(parseDate(iso));
export const fmtMonth = (iso: string) => month.format(parseDate(iso));
export const fmtDayShort = (iso: string) =>
  `${fmtWeekday(iso)} ${fmtDayNumber(iso)} ${fmtMonth(iso)}`;

export function fmtDuration(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function maskPhone(phone: string) {
  return phone.length > 4 ? `•••• ${phone.slice(-4)}` : phone;
}

export function initials(name: string) {
  return name
    .replace(/^Dr\.?\s*/i, "")
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function groupSlotsByDay(slots: DoctorSlot[]) {
  const groups = new Map<string, { key: string; label: string; slots: DoctorSlot[] }>();
  const sorted = [...slots].sort(
    (a, b) => parseDate(a.starts_at).getTime() - parseDate(b.starts_at).getTime(),
  );

  for (const slot of sorted) {
    const key = dayKey.format(parseDate(slot.starts_at));
    const group = groups.get(key) ?? { key, label: fmtDayShort(slot.starts_at), slots: [] };
    group.slots.push(slot);
    groups.set(key, group);
  }

  return [...groups.values()];
}