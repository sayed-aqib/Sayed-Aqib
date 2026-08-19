import { useState } from "react";
import { Overview } from "./pages/Overview";
import { UnitEconomics } from "./pages/UnitEconomics";
import { Funnel } from "./pages/Funnel";
import { Retention } from "./pages/Retention";
import { Keywords } from "./pages/Keywords";
import { MetaAds } from "./pages/MetaAds";

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
          <span className="font-semibold text-ink">Hayah Care · Growth Analytics</span>
          <nav className="flex gap-1">
            {(Object.keys(PAGES) as PageKey[]).map((key) => (
              <button
                key={key}
                onClick={() => setPage(key)}
                className={`rounded px-3 py-1.5 text-sm ${
                  page === key ? "bg-ink text-surface" : "text-ink-muted hover:bg-border/60 hover:text-ink"
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
