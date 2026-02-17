type MarkdownLiteProps = {
  content: string;
  className?: string;
};

function renderInline(value: string): string {
  return value
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

export function MarkdownLite({ content, className = "" }: MarkdownLiteProps) {
  const lines = content.split("\n");

  return (
    <div className={`space-y-1 text-sm leading-6 text-slate-700 ${className}`}>
      {lines.map((line, index) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={`line-${index}`} className="h-2" />;
        }
        if (trimmed.startsWith("- ")) {
          return (
            <div key={`line-${index}`} className="flex gap-2">
              <span>•</span>
              <span
                dangerouslySetInnerHTML={{ __html: renderInline(trimmed.slice(2)) }}
              />
            </div>
          );
        }
        const numbered = trimmed.match(/^(\d+)\.\s+(.+)/);
        if (numbered) {
          return (
            <div key={`line-${index}`} className="flex gap-2">
              <span>{numbered[1]}.</span>
              <span dangerouslySetInnerHTML={{ __html: renderInline(numbered[2]) }} />
            </div>
          );
        }
        return (
          <p
            key={`line-${index}`}
            dangerouslySetInnerHTML={{ __html: renderInline(trimmed) }}
          />
        );
      })}
    </div>
  );
}
