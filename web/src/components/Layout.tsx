import clsx from "clsx";
import { NavLink, Outlet } from "react-router-dom";

import { ScopeSelector } from "./ScopeSelector";
import { ThemeToggle } from "./ThemeToggle";

const links = [
  { to: "/", label: "总览", end: true },
  { to: "/models", label: "模型" },
  { to: "/latency", label: "延迟" },
  { to: "/events", label: "事件" },
  { to: "/sync", label: "同步" },
  { to: "/settings", label: "设置" },
];

export function Layout() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="border-b border-line">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-4 flex flex-col gap-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
            <div className="flex items-center justify-between gap-4">
              <div className="flex flex-col">
                <span className="text-xs uppercase tracking-widest text-text-dim">
                  Cloudflare AI Gateway
                </span>
                <span className="text-lg font-semibold">本地分析面板</span>
              </div>
              <div className="xl:hidden">
                <ThemeToggle />
              </div>
            </div>
            <nav className="flex gap-1 flex-1 overflow-x-auto">
              {links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) =>
                    clsx(
                      "px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-colors",
                      isActive
                        ? "bg-bg-panel text-text shadow-sm"
                        : "text-text-dim hover:bg-bg-subtle hover:text-text"
                    )
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>
            <div className="hidden xl:block">
              <ThemeToggle />
            </div>
          </div>
          <ScopeSelector />
        </div>
      </header>
      <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
