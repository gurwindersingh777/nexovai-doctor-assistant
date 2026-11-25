export function SectionHeading({title, meta}: { title: string; meta?: string }) {
  return (
    <div className="mb-4 flex items-baseline justify-between gap-4">
      <h2 className="font-display text-3xl tracking-tight">{title}</h2>
      {meta && (
        <span className="text-xs tabular-nums text-muted-foreground">
          {meta}
        </span>
      )}
    </div>
  );
}