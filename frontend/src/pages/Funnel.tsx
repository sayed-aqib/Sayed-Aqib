import { EmptyState } from "../components/EmptyState";

export function Funnel() {
  return (
    <div className="space-y-2">
      <h2 className="text-lg font-semibold text-ink">Funnel</h2>
      <EmptyState
        title="Not built yet — Step 3 of the build order"
        instruction="Sessions → add to cart → checkout started → purchase for Shopify, and sessions → unit session % → units by child ASIN for Amazon."
      />
    </div>
  );
}
