/** 表对摘要卡：/pairs 与 /batches/new 共用。 */
import type { Pair } from '../../types/models';
import { PAIR_STATUS_LABELS } from '../../constants/enums';
import { formatInt } from '../../utils/formatNumber';
import { StatusSeal } from './StatusSeal';

interface Props {
  pair: Pair;
  compact?: boolean;
  selected?: boolean;
}

export function PairSummaryCard({ pair, compact, selected }: Props) {
  return (
    <div className={`panel ${selected ? 'is-selected' : ''}`} style={{ marginBottom: compact ? 14 : 26 }}>
      <div className="panel__head">
        <h2 style={{ fontSize: compact ? 'var(--step-1)' : undefined }}>
          {pair.display_name}
          <span className="mono muted" style={{ fontSize: 'var(--step--1)', marginLeft: 10 }}>
            {pair.code}
          </span>
        </h2>
        <StatusSeal
          status={pair.status}
          label={PAIR_STATUS_LABELS[pair.status] || pair.status}
          tone={pair.status === 'active' ? 'green' : 'muted'}
        />
      </div>
      <div className="row mono muted" style={{ fontSize: 'var(--step--1)', gap: 18 }}>
        <span>
          {pair.src_table} → {pair.tgt_table}
        </span>
        <span>PK {pair.primary_key}</span>
        <span>字段 {pair.field_count}</span>
        {pair.is_core ? (
          <span style={{ color: 'var(--vermillion)' }}>● 上线评审核心表</span>
        ) : (
          <span className="muted">○ 非核心表</span>
        )}
      </div>
      {!compact ? <p style={{ margin: '10px 0 6px', color: 'var(--ink-soft)' }}>{pair.description}</p> : null}
      <div className="row mono" style={{ fontSize: 'var(--step--1)', marginTop: 8 }}>
        <span>
          源端 <b>{formatInt(pair.row_estimate_src)}</b> 行
        </span>
        <span>
          目标端 <b>{formatInt(pair.row_estimate_tgt)}</b> 行
        </span>
        <span className="muted">负责人 {pair.owner}</span>
      </div>
    </div>
  );
}
