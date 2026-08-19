import { useState } from "react";
import { Overview } from "./pages/Overview";
import { UnitEconomics } from "./pages/UnitEconomics";
import { Funnel } from "./pages/Funnel";
import { Retention } from "./pages/Retention";
import { Keywords } from "./pages/Keywords";
import { MetaAds } from "./pages/MetaAds";
import { CoinsIcon, FunnelIcon, MegaphoneIcon, OverviewIcon, RetentionIcon, SearchIcon } from "./components/icons";

const PAGES = {
  overview: { label: "Overview", component: Overview, icon: OverviewIcon },
  "unit-economics": { label: "Unit Economics", component: UnitEconomics, icon: CoinsIcon },
  funnel: { label: "Funnel", component: Funnel, icon: FunnelIcon },
  retention: { label: "Retention", component: Retention, icon: RetentionIcon },
  keywords: { label: "Amazon Keywords", component: Keywords, icon: SearchIcon },
  "meta-ads": { label: "Meta Ads", component: MetaAds, icon: MegaphoneIcon },
} as const;

type PageKey = keyof typeof PAGES;

function App() {
  const [page, setPage] = useState<PageKey>("unit-economics");
  const Page = PAGES[page].component;

  return (
    <div className="flex min-h-screen bg-surface">
      <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-panel">
        <div className="border-b border-border bg-gradient-to-b from-brand/[0.07] to-transparent px-5 py-5">
          <img src="/images/hayahcare-logo.png" alt="Hayah Care" className="h-9 w-auto" />
          <p className="mt-1 text-xs text-ink-muted">Growth Analytics</p>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-4">
          {(Object.keys(PAGES) as PageKey[]).map((key) => {
            const { label, icon: Icon } = PAGES[key];
            const active = page === key;
            return (
              <button
                key={key}
                onClick={() => setPage(key)}
                className={`flex w-full items-center gap-2.5 rounded-md border-l-2 px-3 py-2 text-left text-sm transition-colors ${
                  active
                    ? "border-brand-gold bg-brand/[0.07] font-medium text-brand"
                    : "border-transparent text-ink-muted hover:bg-border/40 hover:text-ink"
                }`}
              >
                <Icon className="shrink-0" />
                {label}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-border px-5 py-3 text-xs text-ink-muted">Local · no auth · v1</div>
      </aside>

      <main className="min-w-0 flex-1 bg-[linear-gradient(150deg,#eef2e8_0%,#fafaf8_38%,#fafaf8_62%,#f7f1e4_100%)] px-8 py-8">
        <div className="mx-auto max-w-5xl">
          <Page />
        </div>
      </main>
    </div>
  );
}

export default App;
