import { useId } from "react";
import { Check, Info } from "lucide-react";

import { ASSISTANT_CAN, ASSISTANT_LIMITS } from "@/lib/assistant-guide";

/**
 * What the assistant can answer and where it stops. Side by side in the
 * narrow-screen toggle panel; the desktop sidebar passes a stacked layout.
 */
export function AssistantGuide({
  className = "grid gap-5 text-sm sm:grid-cols-2",
}: {
  className?: string;
}) {
  // Both the sidebar and the toggle panel can be in the DOM at once, so the
  // heading ids must be unique per instance.
  const id = useId();
  return (
    <div className={className}>
      <section aria-labelledby={`${id}-can`}>
        <h2
          id={`${id}-can`}
          className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase"
        >
          You can ask it to
        </h2>
        <ul className="space-y-2">
          {ASSISTANT_CAN.map((item) => (
            <li key={item.title} className="flex gap-2">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" aria-hidden />
              <span>
                <span className="block text-slate-800">{item.title}</span>
                <span className="block text-xs text-slate-500">{item.example}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby={`${id}-limits`}>
        <h2
          id={`${id}-limits`}
          className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase"
        >
          Good to know
        </h2>
        <ul className="space-y-2">
          {ASSISTANT_LIMITS.map((limit) => (
            <li key={limit} className="flex gap-2 text-slate-600">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden />
              <span>{limit}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
