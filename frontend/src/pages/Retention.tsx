import { EmptyState } from "../components/EmptyState";

export function Retention() {
  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold text-ink">Retention</h2>
      <EmptyState
        title="Not built yet — Step 4 of the build order"
        instruction="Repeat purchase rate, days between first and second order, monthly cohorts, and the Chukku Kappi → Supermix cross-sell path."
      />
    </div>
  );
}
