type ChatTableProps = {
  columns: string[];
  rows: string[][];
};

export function ChatTable({ columns, rows }: ChatTableProps) {
  if (columns.length === 0 || rows.length === 0) {
    return null;
  }

  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-xs">
        <thead className="bg-slate-100 text-left uppercase tracking-wide text-slate-600">
          <tr>
            {columns.map((column) => (
              <th key={column} className="px-2 py-1.5 font-semibold">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={`row-${rowIndex}`} className="odd:bg-white even:bg-slate-50">
              {row.map((cell, cellIndex) => (
                <td key={`cell-${rowIndex}-${cellIndex}`} className="px-2 py-1.5 text-slate-700">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
