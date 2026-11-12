import type { ReactNode } from 'react';

interface Props {
  title: string;
  hints: string[];
  action?: ReactNode;
}

export function EmptyState({ title, hints, action }: Props) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {hints.map((hint) => (
        <div key={hint}>· {hint}</div>
      ))}
      {action ? <div style={{ marginTop: 14 }}>{action}</div> : null}
    </div>
  );
}
