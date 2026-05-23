import clsx from "clsx";

import type { InsightItem } from "@/api/types";

type Props = {
  items: InsightItem[] | undefined;
};

export function InsightsList({ items }: Props) {
  if (!items || items.length === 0) return null;
  return (
    <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {items.map((item, idx) => (
        <li
          key={`${item.title}-${idx}`}
          className={clsx(
            "panel-sm border-l-4 flex flex-col gap-1",
            item.level === "warning" && "border-l-warning",
            item.level === "danger" && "border-l-danger",
            item.level === "info" && "border-l-accent"
          )}
        >
          <span className="text-xs uppercase tracking-wider text-text-dim">
            {item.title}
          </span>
          <span className="text-sm text-text">{item.detail}</span>
        </li>
      ))}
    </ul>
  );
}
