/** 账簿表格：横线底稿样式 + 列定义渲染。至少 /pairs /batches/:id /diffs /tickets 共用。 */
import type { ReactNode } from 'react';

export interface LedgerColumn<T> {
  key: string;
  label: string;
  align?: 'left' | 'right';
  width?: string;
  render: (row: T) => ReactNode;
}

interface Props<T> {
  columns: LedgerColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  emptyHint?: ReactNode;
}

export function LedgerTable<T>({ columns, rows, rowKey, emptyHint }: Props<T>) {
  if (rows.length === 0) {
    return <div className="empty-state">{emptyHint || '暂无记录：调整筛选条件或先运行一个对账批次。'}</div>;
  }
  return (
    <div className="table-scroll">
      <table className="ledger-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} style={{ width: column.width, textAlign: column.align || 'left' }}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} style={{ textAlign: column.align || 'left' }}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
