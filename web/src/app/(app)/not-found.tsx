import Link from "next/link";

export default function NotFound() {
  return (
    <div className="grid place-items-center py-24 text-center">
      <p className="text-sm font-medium text-slate-400">404</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Not found</h1>
      <p className="mt-2 max-w-md text-sm text-slate-600">
        That candidate or role is not in the database. It may have been removed, or the link may
        have been mistyped.
      </p>
      <Link
        href="/"
        className="mt-6 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
      >
        Back to the dashboard
      </Link>
    </div>
  );
}
