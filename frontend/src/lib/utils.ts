import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDate(date: string | Date): string {
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(date: string | Date): string {
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelativeTime(date: string | Date): string {
  const now = Date.now();
  const then = new Date(date).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(date);
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    active: "text-green-600 bg-green-50 dark:bg-green-950/30 dark:text-green-400",
    draft: "text-yellow-600 bg-yellow-50 dark:bg-yellow-950/30 dark:text-yellow-400",
    completed: "text-blue-600 bg-blue-50 dark:bg-blue-950/30 dark:text-blue-400",
    failed: "text-red-600 bg-red-50 dark:bg-red-950/30 dark:text-red-400",
    pending: "text-gray-600 bg-gray-50 dark:bg-gray-800 dark:text-gray-400",
    in_progress: "text-indigo-600 bg-indigo-50 dark:bg-indigo-950/30 dark:text-indigo-400",
    approved: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30 dark:text-emerald-400",
    cancelled: "text-gray-500 bg-gray-100 dark:bg-gray-800 dark:text-gray-500",
    repealed: "text-red-600 bg-red-50 dark:bg-red-950/30 dark:text-red-400",
    superseded: "text-orange-600 bg-orange-50 dark:bg-orange-950/30 dark:text-orange-400",
  };
  return colors[status] || colors.pending;
}

export function getRiskLevelColor(level: string): string {
  const colors: Record<string, string> = {
    low: "text-green-600 bg-green-50 dark:bg-green-950/30 dark:text-green-400",
    medium: "text-yellow-600 bg-yellow-50 dark:bg-yellow-950/30 dark:text-yellow-400",
    high: "text-orange-600 bg-orange-50 dark:bg-orange-950/30 dark:text-orange-400",
    critical: "text-red-600 bg-red-50 dark:bg-red-950/30 dark:text-red-400",
  };
  return colors[level] || colors.low;
}

export function truncate(str: string, length = 100): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + "...";
}
