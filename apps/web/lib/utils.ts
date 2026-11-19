import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const idx = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** idx).toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function statusColorClasses(status: string): string {
  const s = (status || "").toUpperCase();
  if (["FOUND", "APPROVED", "COMPLETED", "HIGH", "OFFICER_APPROVED", "AUTO_PREPARED"].includes(s)) {
    return "bg-emerald-50 text-emerald-700 border-emerald-200";
  }
  if (["PENDING_REVIEW", "AWAITING_REVIEW", "PROCESSING", "QUEUED", "MEDIUM", "CONDITIONAL", "MANUALLY_REVIEWED", "QUALITY_CHECKED"].includes(s)) {
    return "bg-amber-50 text-amber-700 border-amber-200";
  }
  if (["MISSING", "FAILED", "UNREADABLE", "POTENTIALLY_INVALID", "LOW", "MANUAL_REQUIRED", "EXCLUDED"].includes(s)) {
    return "bg-red-50 text-red-700 border-red-200";
  }
  return "bg-slate-100 text-slate-700 border-slate-200";
}
