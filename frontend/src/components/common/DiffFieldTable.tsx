/** 差异行对照表：源值/目标值双列，分类与相似度由后端算法给出。 */
import type { Diff } from '../../types/models';
import { DIFF_TYPE_LABELS } from '../../constants/enums';
import { LedgerTable } from './LedgerTable';
import type { LedgerColumn } from './LedgerTable';

interface Props {
  diffs: Diff[];
  onPick?: (diff: Diff) => void;
  selectedIds?: number[];
}

export function DiffFieldTable({ diffs, onPick, selectedIds }: Props) {
  const columns: LedgerColumn<Diff>[] = [
        {
          key: 'bucket',
          label: '桶',
          width: '54px',
          render: (row) => <span className="mono">{row.bucket_no}</span>,
        },
        {
          key: 'key',
          label: '主键',
          width: '128px',
          render: (row) => <span className="mono">{row.primary_key_value}</span>,
        },
        {
          key: 'field',
          label: '字段 / 类型',
          width: '128px',
          render: (row) => (
            <div>
              <div className="mono">{row.field_name === '__row__' ? '整行' : row.field_name}</div>
              <div className={`mono ${row.diff_type === 'missing' || row.diff_type === 'extra' ? 'red' : 'muted'}`} style={{ fontSize: 'var(--step--1)' }}>
                {DIFF_TYPE_LABELS[row.diff_type] || row.diff_type}
              </div>
            </div>
          ),
        },
        {
          key: 'values',
          label: '源值 → 目标值',
          render: (row) => (
            <div className="diff-pair">
              <div className="is-src">
                <small>source</small>
                {row.src_value === null ? <span className="muted">（无）</span> : row.src_value}
              </div>
              <div className="is-tgt">
                <small>target</small>
                {row.tgt_value === null ? <span className="muted">（无）</span> : row.tgt_value}
              </div>
            </div>
          ),
        },
        {
          key: 'similarity',
          label: '相似度',
          width: '78px',
          align: 'right',
          render: (row) => <span className="mono">{row.similarity.toFixed(4)}</span>,
        },
        {
          key: 'attr',
          label: '归因 / 建议',
          render: (row) => (
            <div style={{ fontSize: 'var(--step--1)' }}>
              <div>{row.attribution}</div>
              <div className="muted">{row.suggestion}</div>
            </div>
          ),
        },
  ];
  if (onPick) {
    columns.push({
      key: 'pick',
      label: '纳入',
      width: '56px',
      render: (row: Diff) => (
        <input
          type="checkbox"
          checked={(selectedIds || []).includes(row.id)}
          onChange={() => onPick(row)}
          style={{ accentColor: 'var(--vermillion)', width: 15, height: 15 }}
        />
      ),
    });
  }
  return (
    <LedgerTable<Diff>
      rows={diffs}
      rowKey={(row) => row.id}
      emptyHint="该筛选下没有差异行：换一个桶、表对或差异类型。"
      columns={columns}
    />
  );
}
