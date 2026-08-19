export function EmptyState({ title, instruction }: { title: string; instruction: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border p-10 text-center">
      <p className="font-medium text-ink">{title}</p>
      <p className="mt-1 text-sm text-ink-muted">{instruction}</p>
    </div>
  );
}
