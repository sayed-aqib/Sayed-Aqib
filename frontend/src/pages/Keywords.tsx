import { EmptyState } from "../components/EmptyState";

export function Keywords() {
  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold text-ink">Amazon Keywords</h2>
      <EmptyState
        title="Not built yet — Step 5 of the build order"
        instruction="Impression share vs. conversion share per search query, split into listing-problem queries and price-problem queries."
      />
    </div>
  );
}
