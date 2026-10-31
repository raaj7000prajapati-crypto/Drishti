import React from 'react';
import { Clock } from 'lucide-react';
import { PageState, Surface } from './ui';

export default function CaseTimeline({ events = [] }) {
  return (
    <Surface className="p-6">
      <h2 className="mb-6 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-slate-900">
        <Clock className="h-4 w-4 text-amber-600" aria-hidden="true" />
        Case timeline
      </h2>
      {events.length === 0 ? (
        <PageState
          type="empty"
          title="No timeline events yet"
          description="Case updates and decisions will appear here."
          className="p-6"
        />
      ) : (
        <ol
          aria-label="Case event history"
          className="relative space-y-5 pl-6 before:absolute before:bottom-2 before:left-2.5 before:top-2 before:w-0.5 before:bg-slate-200"
        >
          {events.map((event) => (
            <li key={event.id} className="relative">
              <span
                className="absolute -left-6 top-1 h-3.5 w-3.5 rounded-full border-2 border-white bg-amber-500 shadow"
                aria-hidden="true"
              />
              <article className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h3 className="text-xs font-bold text-slate-900">{event.title}</h3>
                  <time
                    className="text-[10px] text-slate-500"
                    dateTime={event.created_at}
                  >
                    {new Date(event.created_at).toLocaleString([], {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </time>
                </div>
                {event.description && (
                  <p className="mt-1 text-xs leading-relaxed text-slate-600">
                    {event.description}
                  </p>
                )}
                <p className="mt-1.5 text-[10px] italic text-slate-500">
                  Action by: {event.actor_name || 'System'}
                </p>
              </article>
            </li>
          ))}
        </ol>
      )}
    </Surface>
  );
}
