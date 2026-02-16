import { PropsWithChildren, ReactNode } from "react";

type SectionTitleProps = PropsWithChildren<{
  title: string;
  subtitle?: string;
  right?: ReactNode;
}>;

export function SectionTitle({ title, subtitle, right }: SectionTitleProps) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-xl font-bold text-slate-900">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
