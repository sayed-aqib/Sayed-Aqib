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
    <div
      className="flex min-h-screen"
      style={{
        background:
          "radial-gradient(900px circle at 12% 8%, rgba(45,106,79,0.14), transparent 55%), " +
          "radial-gradient(700px circle at 92% 18%, rgba(156,107,46,0.12), transparent 55%), " +
          "radial-gradient(800px circle at 75% 90%, rgba(45,106,79,0.10), transparent 55%), " +
          "radial-gradient(600px circle at 15% 85%, rgba(179,64,46,0.06), transparent 55%), " +
          "linear-gradient(150deg, #eef2e8 0%, #fafaf8 45%, #fafaf8 60%, #f7f1e4 100%)",
      }}
    >
      <aside className="flex w-60 shrink-0 flex-col border-r border-white/50 bg-panel/70 backdrop-blur-xl">
        <div className="border-b border-white/50 px-5 py-5">
          <img src="/images/hayahcare-logo.png" alt="Hayah Care" className="h-10 w-auto" />
          <p className="mt-1.5 text-xs tracking-wide text-ink-muted uppercase">Growth Analytics</p>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-4">
          {(Object.keys(PAGES) as PageKey[]).map((key) => {
            const { label, icon: Icon } = PAGES[key];
            const active = page === key;
            return (
              <button
                key={key}
                onClick={() => setPage(key)}
                className={`flex w-full items-center gap-2.5 rounded-full px-3.5 py-2 text-left text-sm transition-colors ${
                  active
                    ? "border border-brand/15 bg-white/70 font-medium text-brand shadow-[0_1px_3px_rgba(31,64,50,0.12)] backdrop-blur-md"
                    : "border border-transparent text-ink-muted hover:bg-white/40 hover:text-ink"
                }`}
              >
                <Icon className="shrink-0" />
                {label}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-white/50 px-5 py-3 text-xs text-ink-muted">Local · no auth · v1</div>
      </aside>

      <main className="min-w-0 flex-1 px-8 py-8">
        <div className="mx-auto max-w-5xl">
          <Page />
        </div>
      </main>
    </div>
  );
}

export default App;
