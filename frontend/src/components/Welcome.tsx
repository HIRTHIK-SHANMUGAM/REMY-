import {
  FileSearch,
  Sparkles,
  TerminalSquare,
  Clock,
  type LucideIcon,
} from "lucide-react";

interface Suggestion {
  icon: LucideIcon;
  title: string;
  prompt: string;
}

const SUGGESTIONS: Suggestion[] = [
  {
    icon: FileSearch,
    title: "Summarize a file",
    prompt: "Read the files in my workspace and summarize what's there.",
  },
  {
    icon: TerminalSquare,
    title: "Check system health",
    prompt: "Give me a quick status: disk, CPU, and anything I should know.",
  },
  {
    icon: Clock,
    title: "Schedule a task",
    prompt: "Remind me to review the REMY PR in 2 hours.",
  },
  {
    icon: Sparkles,
    title: "What can you do?",
    prompt: "What are you able to do for me? Give me a short tour.",
  },
];

export function Welcome({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl text-center">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-accent-from to-accent-to text-2xl font-bold text-white shadow-accent-glow">
          R
        </div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">
          How can I help, Hirthik?
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink-muted">
          I'm REMY — I can read and write files, run commands, browse the web,
          and act on my own. Pick a starting point or just type below.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {SUGGESTIONS.map(({ icon: Icon, title, prompt }) => (
            <button
              key={title}
              onClick={() => onPick(prompt)}
              className="group flex items-start gap-3 rounded-xl border border-surface-3 bg-surface-1 p-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-accent/50 hover:bg-surface-2"
            >
              <span className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-accent/12 text-accent transition-colors group-hover:bg-accent/20">
                <Icon size={16} />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-medium text-ink">
                  {title}
                </span>
                <span className="mt-0.5 block truncate text-xs text-ink-faint">
                  {prompt}
                </span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
