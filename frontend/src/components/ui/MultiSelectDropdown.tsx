import { useEffect, useMemo, useRef, useState } from "react";

type MultiSelectDropdownProps = {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  className?: string;
};

export function MultiSelectDropdown({
  options,
  selected,
  onChange,
  placeholder = "Select options",
  className = "",
}: MultiSelectDropdownProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      if (!rootRef.current) {
        return;
      }
      const target = event.target as Node | null;
      if (target && !rootRef.current.contains(target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const selectedPreview = useMemo(() => {
    if (selected.length === 0) {
      return placeholder;
    }
    if (selected.length <= 2) {
      return selected.join(", ");
    }
    return `${selected.length} selected`;
  }, [placeholder, selected]);

  const toggleValue = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((item) => item !== value));
      return;
    }
    onChange([...selected, value]);
  };

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        className="flex h-10 w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-3 text-left text-sm text-slate-800 outline-none transition focus:border-accent focus:ring-2 focus:ring-cyan-100"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className={selected.length === 0 ? "text-slate-400" : "text-slate-800"}>
          {selectedPreview}
        </span>
        <span className="text-xs text-slate-500">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white p-2 shadow-xl">
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              className="text-xs font-semibold text-cyan-700 hover:underline"
              onClick={() => onChange(options)}
            >
              Select all
            </button>
            <button
              type="button"
              className="text-xs font-semibold text-slate-500 hover:underline"
              onClick={() => onChange([])}
            >
              Clear
            </button>
          </div>
          <ul className="space-y-1">
            {options.map((option) => (
              <li key={option}>
                <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50">
                  <input
                    type="checkbox"
                    checked={selected.includes(option)}
                    onChange={() => toggleValue(option)}
                  />
                  <span>{option}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
