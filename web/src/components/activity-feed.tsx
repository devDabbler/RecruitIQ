import Link from "next/link";

import type { ActivityEvent } from "@/lib/domain";
import { formatDate } from "@/lib/format";
import { activityPredicate } from "@/lib/reports";

/** The latest pipeline moves, newest first, straight from the stage history. */
export function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-slate-500">No pipeline activity yet.</p>;
  }
  return (
    <ol className="space-y-3 text-sm">
      {events.map((event, index) => (
        <li
          key={`${event.at}-${event.candidate_id}-${event.kind}-${index}`}
          className="flex items-baseline justify-between gap-3"
        >
          <span className="min-w-0">
            <Link href={`/candidates/${event.candidate_id}`} className="font-medium hover:underline">
              {event.candidate_name}
            </Link>{" "}
            <span className="text-slate-600">{activityPredicate(event)}</span>
            {event.actor_name ? (
              <span className="block text-xs text-slate-400">by {event.actor_name}</span>
            ) : null}
          </span>
          <time dateTime={event.at} className="shrink-0 text-xs text-slate-400">
            {formatDate(event.at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
