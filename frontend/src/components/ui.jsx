import React from 'react';
import { AlertTriangle, Inbox } from 'lucide-react';

const STATUS_CLASSES = {
  New: 'bg-blue-100 text-blue-800 border-blue-200',
  Assigned: 'bg-purple-100 text-purple-800 border-purple-200',
  'In Progress': 'bg-amber-100 text-amber-800 border-amber-200',
  'Awaiting Info': 'bg-cyan-100 text-cyan-800 border-cyan-200',
  Overdue: 'bg-red-100 text-red-800 border-red-200',
  Closed: 'bg-emerald-100 text-emerald-800 border-emerald-200',
};

export function Surface({ as: Element = 'section', className = '', children, ...props }) {
  return (
    <Element
      className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}
      {...props}
    >
      {children}
    </Element>
  );
}

export function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${
        STATUS_CLASSES[status] || 'bg-slate-100 text-slate-800 border-slate-200'
      }`}
    >
      {status}
    </span>
  );
}

export function PageState({
  type = 'empty',
  title,
  description,
  actionLabel,
  onAction,
  className = '',
}) {
  const isLoading = type === 'loading';
  const isError = type === 'error';
  const RoleIcon = isError ? AlertTriangle : Inbox;

  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 p-10 text-center ${className}`}
      role={isError ? 'alert' : 'status'}
      aria-live={isError ? 'assertive' : 'polite'}
      aria-busy={isLoading}
    >
      {isLoading ? (
        <span
          className="h-7 w-7 animate-spin rounded-full border-2 border-amber-500 border-t-transparent"
          aria-hidden="true"
        />
      ) : (
        <RoleIcon
          className={`h-8 w-8 ${isError ? 'text-red-500' : 'text-slate-300'}`}
          aria-hidden="true"
        />
      )}
      <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
      {description && <p className="max-w-md text-xs text-slate-500">{description}</p>}
      {onAction && actionLabel && (
        <button
          type="button"
          onClick={onAction}
          className="mt-2 rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
