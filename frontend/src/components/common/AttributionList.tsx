/** 归因摘要：后端按 (表, 字段, 分类) 聚合，前端只展示。 */
import type { DiffSummary } from '../../types/models';
import { DIFF_TYPE_LABELS } from '../../constants/enums';

export function AttributionList({ summary, limit = 6 }: { summary: DiffSummary; limit?: number }) {
  if (summary.groups.length === 0) {
    return <div className="empty-state">本批次没有差异，无需归因。</div>;
  }
  return (
    <ol className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {summary.groups.slice(0, limit).map((group) => (
        <li key={`${group.pair_code}-${group.field_name}-${group.diff_type}`}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span>
              <b className="mono">{group.table}</b>
              <span className="mono muted"> · {group.field_label} · </span>
              <span className="red mono">{DIFF_TYPE_LABELS[group.diff_type] || group.diff_type}</span>
            </span>
            <span className="mono">
              {group.count} 行 <span className="muted">（{(group.ratio * 100).toFixed(1)}%）</span>
            </span>
          </div>
          <div className="mono muted" style={{ fontSize: 'var(--step--1)' }}>
            最可能原因：{group.root_cause}
          </div>
          <div className="mono" style={{ fontSize: 'var(--step--1)' }}>
            建议：{group.suggestion}
          </div>
        </li>
      ))}
    </ol>
  );
}
