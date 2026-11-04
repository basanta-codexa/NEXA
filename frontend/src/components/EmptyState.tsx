import type { ReactNode } from "react";

export default function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      {icon ? <div style={{ fontSize: 28, marginBottom: 8 }}>{icon}</div> : null}
      <div style={{ fontWeight: 700, color: "var(--text)", marginBottom: 4 }}>
        {title}
      </div>
      {hint ? <div style={{ fontSize: 12, marginBottom: 12 }}>{hint}</div> : null}
      {action}
    </div>
  );
}
