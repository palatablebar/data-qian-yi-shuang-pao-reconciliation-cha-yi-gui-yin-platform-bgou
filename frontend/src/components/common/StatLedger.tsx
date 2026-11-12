/** 统计横线：底稿抬头的一组关键数值。 */
import type { ReactNode } from 'react';

export interface StatCell {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: 'red' | 'green';
}

export function StatLedger({ cells }: { cells: StatCell[] }) {
  return (
    <div className="stat-ledger">
      {cells.map((cell) => (
        <div className="stat-ledger__cell" key={cell.label}>
          <div className="stat-ledger__label">{cell.label}</div>
          <div className={`stat-ledger__value ${cell.tone ? `is-${cell.tone}` : ''}`}>{cell.value}</div>
          {cell.hint ? <div className="stat-ledger__hint">{cell.hint}</div> : null}
        </div>
      ))}
    </div>
  );
}
