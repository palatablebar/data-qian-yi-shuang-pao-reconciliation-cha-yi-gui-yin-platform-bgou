/** /diffs 差异明细下钻：字段级对照 + 分类筛选 + 桶矩阵跳转入口。 */
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getBatch, getBuckets } from '../api/batches';
import { exportDiffs, getSummary, listDiffs } from '../api/diffs';
import { BucketMatrix } from '../components/common/BucketMatrix';
import { DiffFieldTable } from '../components/common/DiffFieldTable';
import { ErrorNote } from '../components/common/ErrorNote';
import { LoadingRule } from '../components/common/LoadingRule';
import { DIFF_TYPE_LABELS } from '../constants/enums';
import type { Batch, Bucket, Diff, DiffSummary } from '../types/models';
import { errorMessage } from '../utils/errorMessage';
import { formatInt } from '../utils/formatNumber';

const PRESETS = [
  { label: 'order_item.qty 类型截断', pair: 'order_item', field: 'qty', type: 'type_truncated' },
  { label: 'customer.phone 编码差异', pair: 'customer', field: 'phone', type: 'encoding' },
  { label: '整行缺失', pair: '', field: '__row__', type: 'missing' },
];

export function Diffs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const batchId = searchParams.get('batch_id') ? Number(searchParams.get('batch_id')) : null;
  const pairCode = searchParams.get('pair_code') || '';
  const fieldName = searchParams.get('field_name') || '';
  const diffType = searchParams.get('diff_type') || '';
  const bucketNo = searchParams.get('bucket_no') ? Number(searchParams.get('bucket_no')) : null;

  const [batch, setBatch] = useState<Batch | null>(null);
  const [buckets, setBuckets] = useState<Bucket[]>([]);
  const [diffs, setDiffs] = useState<Diff[]>([]);
  const [summary, setSummary] = useState<DiffSummary | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (batchId === null) {
      setBatch(null);
      setBuckets([]);
      setSummary(null);
      return;
    }
    getBatch(batchId).then(setBatch).catch(() => undefined);
    getBuckets(batchId)
      .then((data) => setBuckets(data.items))
      .catch(() => undefined);
    getSummary(batchId)
      .then(setSummary)
      .catch(() => undefined);
  }, [batchId]);

  useEffect(() => {
    setLoading(true);
    listDiffs({
      batch_id: batchId ?? undefined,
      pair_code: pairCode || undefined,
      field_name: fieldName || undefined,
      diff_type: diffType || undefined,
      bucket_no: bucketNo ?? undefined,
      limit: 200,
    })
      .then((data) => {
        setDiffs(data.items);
        setError('');
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [batchId, pairCode, fieldName, diffType, bucketNo]);

  const updateParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  };

  const applyPreset = (preset: (typeof PRESETS)[number]) => {
    const next = new URLSearchParams(searchParams);
    if (preset.pair) next.set('pair_code', preset.pair);
    else next.delete('pair_code');
    next.set('field_name', preset.field);
    next.set('diff_type', preset.type);
    next.delete('bucket_no');
    setSearchParams(next);
  };

  const typeChips = useMemo(() => summary?.by_type || [], [summary]);
  const activeBucket = bucketNo;

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-head__kicker">Schedule 05 · 差异下钻</div>
          <h1>差异明细与字段对照</h1>
        </div>
        <div className="page-head__meta">
          {batch ? (
            <>
              批次 {batch.batch_no} · {batch.pair_codes.join(' / ')}
              <br />
              差异类型 / 桶 / 表对三重筛选，只展示后端落库的 diff_detail
            </>
          ) : (
            '选择批次后可查看桶矩阵与归因'
          )}
        </div>
      </header>

      {error ? <ErrorNote message={error} title="读取失败" /> : null}

      {batch ? (
        <section className="panel">
          <div className="panel__head">
            <h2 style={{ fontSize: 'var(--step-1)' }}>桶矩阵跳转</h2>
            <span className="panel__note">
              {batch.buckets_mismatched} 个不一致桶 · 点击红色桶只看该桶差异
            </span>
          </div>
          <BucketMatrix
            buckets={buckets}
            bucketCount={batch.bucket_count}
            compact
            activeBucket={activeBucket}
            onSelect={(bucket) => updateParam('bucket_no', String(bucket))}
          />
        </section>
      ) : null}

      <div className="chip-row">
        {PRESETS.map((preset) => (
          <button className="chip" type="button" key={preset.label} onClick={() => applyPreset(preset)}>
            {preset.label}
          </button>
        ))}
        {typeChips.map((item) => (
          <button
            className={`chip ${diffType === item.diff_type ? 'is-active' : ''}`}
            type="button"
            key={item.diff_type}
            onClick={() => updateParam('diff_type', diffType === item.diff_type ? '' : item.diff_type)}
          >
            {DIFF_TYPE_LABELS[item.diff_type] || item.diff_type} {item.count}
          </button>
        ))}
        {bucketNo !== null ? (
          <button className="chip is-active" type="button" onClick={() => updateParam('bucket_no', '')}>
            桶 {bucketNo} ×
          </button>
        ) : null}
        {(pairCode || fieldName || diffType) && (
          <button className="chip" type="button" onClick={() => setSearchParams(batchId ? { batch_id: String(batchId) } : {})}>
            清空筛选
          </button>
        )}
      </div>

      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
        <span className="mono" style={{ fontSize: 'var(--step--1)' }}>
          命中 {formatInt(diffs.length)} 行差异（上限 200）
          {pairCode ? ` · 表对 ${pairCode}` : ''}
          {fieldName ? ` · 字段 ${fieldName}` : ''}
        </span>
        <div className="row">
          <button
            className="btn btn--ghost"
            type="button"
            onClick={() => exportDiffs(batchId ?? 0, pairCode || undefined).catch((err) => setError(errorMessage(err)))}
          >
            导出差异 CSV
          </button>
        </div>
      </div>

      {loading ? <LoadingRule label="正在读取差异明细…" /> : <DiffFieldTable diffs={diffs} />}
    </>
  );
}
