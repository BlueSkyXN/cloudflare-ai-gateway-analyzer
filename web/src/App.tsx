import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { EventsPage } from "./pages/EventsPage";
import { LatencyPage } from "./pages/LatencyPage";
import { ModelsPage } from "./pages/ModelsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SyncConsolePage } from "./pages/SyncConsolePage";

export default function App() {
  return (
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
  );
}
