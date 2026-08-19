import { useState } from "react";
import { Overview } from "./pages/Overview";
import { UnitEconomics } from "./pages/UnitEconomics";
import { Funnel } from "./pages/Funnel";
import { Retention } from "./pages/Retention";
import { Keywords } from "./pages/Keywords";
import { MetaAds } from "./pages/MetaAds";
import { BrandMark } from "./components/BrandMark";

const PAGES = {
  overview: { label: "Overview", component: Overview },
  "unit-economics": { label: "Unit Economics", component: UnitEconomics },
  funnel: { label: "Funnel", component: Funnel },
  retention: { label: "Retention", component: Retention },
  keywords: { label: "Amazon Keywords", component: Keywords },
  "meta-ads": { label: "Meta Ads", component: MetaAds },
} as const;

type PageKey = keyof typeof PAGES;

function App() {
  const [page, setPage] = useState<PageKey>("unit-economics");
  const Page = PAGES[page].component;

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b-2 border-brand bg-panel">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <span className="flex items-center gap-2">
            <BrandMark />
            <span>
              <span className="font-semibold text-brand">Hayah Care</span>
              <span className="text-ink-muted"> · Growth Analytics</span>
            </span>
          </span>
          <nav className="flex gap-1">
            {(Object.keys(PAGES) as PageKey[]).map((key) => (
              <button
                key={key}
                onClick={() => setPage(key)}
                className={`rounded-t px-3 py-1.5 text-sm transition-colors ${
                  page === key
                    ? "border-b-2 border-brand-gold font-medium text-brand"
                    : "border-b-2 border-transparent text-ink-muted hover:text-ink"
                }`}
              >
                {PAGES[key].label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        <Page />
      </main>
    </div>
  );
}

export default App;
