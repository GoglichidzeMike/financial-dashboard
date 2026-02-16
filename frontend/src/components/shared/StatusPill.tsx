type StatusPillProps = {
  label: string;
  tone?: "ok" | "warn" | "error" | "neutral";
};

const TONE_CLASS: Record<NonNullable<StatusPillProps["tone"]>, string> = {
  ok: "bg-emerald-100 text-emerald-700",
  warn: "bg-amber-100 text-amber-700",
  error: "bg-rose-100 text-rose-700",
  neutral: "bg-slate-100 text-slate-600",
};

export function StatusPill({ label, tone = "neutral" }: StatusPillProps) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${TONE_CLASS[tone]}`}>
      {label}
    </span>
  );
}
