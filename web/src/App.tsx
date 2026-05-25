import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";

const EventsPage = lazy(() =>
  import("./pages/EventsPage").then((module) => ({ default: module.EventsPage }))
);
const LatencyPage = lazy(() =>
  import("./pages/LatencyPage").then((module) => ({ default: module.LatencyPage }))
);
const ModelsPage = lazy(() =>
  import("./pages/ModelsPage").then((module) => ({ default: module.ModelsPage }))
);
const OverviewPage = lazy(() =>
  import("./pages/OverviewPage").then((module) => ({ default: module.OverviewPage }))
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage }))
);
const SyncConsolePage = lazy(() =>
  import("./pages/SyncConsolePage").then((module) => ({ default: module.SyncConsolePage }))
);

export default function App() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-text-dim">页面加载中...</div>}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/models" element={<ModelsPage />} />
          <Route path="/latency" element={<LatencyPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/sync" element={<SyncConsolePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<OverviewPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
