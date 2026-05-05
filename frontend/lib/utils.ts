import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(d: string | Date | null | undefined, locale = "vi-VN") {
  if (!d) return "—";
  const date = typeof d === "string" ? new Date(d) : d;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function relativeTime(d: string | Date | null | undefined) {
  if (!d) return "—";
  const date = typeof d === "string" ? new Date(d) : d;
  const diff = (Date.now() - date.getTime()) / 1000;
  const units: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "second"],
    [60, "minute"],
    [24, "hour"],
    [7, "day"],
    [4.34524, "week"],
    [12, "month"],
  ];
  let v = diff;
  let unit: Intl.RelativeTimeFormatUnit = "second";
  for (const [div, u] of units) {
    if (Math.abs(v) < div) {
      unit = u;
      break;
    }
    v /= div;
    unit = u;
  }
  return new Intl.RelativeTimeFormat("vi-VN", { numeric: "auto" }).format(
    -Math.round(v),
    unit
  );
}
