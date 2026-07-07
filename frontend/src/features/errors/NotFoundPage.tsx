import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="text-7xl font-bold text-brand-600 dark:text-brand-400">404</div>
      <h1 className="text-2xl font-semibold text-surface-900 dark:text-surface-100">
        Page Not Found
      </h1>
      <p className="max-w-md text-surface-500 dark:text-surface-400">
        The page you are looking for does not exist or has been moved.
      </p>
      <Link
        to="/dashboard"
        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700"
      >
        Go to Dashboard
      </Link>
    </div>
  );
}
