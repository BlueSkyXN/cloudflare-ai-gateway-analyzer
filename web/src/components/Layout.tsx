import clsx from "clsx";
import { NavLink, Outlet } from "react-router-dom";

import { ScopeSelector } from "./ScopeSelector";

const links = [
  { to: "/", label: "Overview", end: true },
  { to: "/models", label: "Models" },
  { to: "/latency", label: "Latency" },
  { to: "/events", label: "Events" },
  { to: "/sync", label: "Sync" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="border-b border-line">
        <div className="max-w-screen-2xl mx-auto px-6 py-4 flex items-center gap-6">
          <div className="flex flex-col">
            <span className="text-xs uppercase tracking-widest text-text-dim">
              Cloudflare AI Gateway
            </span>
            <span className="text-lg font-semibold">Analyzer</span>
          </div>
          <nav className="flex gap-1 ml-4 flex-1 overflow-x-auto">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  clsx(
                    "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                    isActive
                      ? "bg-bg-panel text-text"
                      : "text-text-dim hover:bg-bg-subtle hover:text-text"
                  )
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <ScopeSelector />
        </div>
      </header>
      <main className="max-w-screen-2xl mx-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
