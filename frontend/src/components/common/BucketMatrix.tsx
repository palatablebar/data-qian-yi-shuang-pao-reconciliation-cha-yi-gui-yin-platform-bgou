/** 桶热力矩阵：/batches/:id 全量矩阵 + /diffs 顶部跳转入口（同组件两种密度）。 */
import type { Bucket } from '../../types/models';

interface Props {
  buckets: Bucket[];
  bucketCount: number;
  activeBucket?: number | null;
  onSelect?: (bucketNo: number) => void;
  compact?: boolean;
}

export function BucketMatrix({ buckets, bucketCount, activeBucket, onSelect, compact }: Props) {
  const byNo = new Map<number, Bucket>();
  buckets.forEach((bucket) => byNo.set(bucket.bucket_no, bucket));
  const numbers = Array.from({ length: bucketCount }, (_, index) => index);
  return (
    <div>
      <div className="bucket-matrix" style={compact ? { gridTemplateColumns: 'repeat(32, minmax(0, 1fr))' } : undefined}>
        {numbers.map((bucketNo) => {
          const bucket = byNo.get(bucketNo);
          const status = bucket?.status || 'pending';
          const className = `bucket-cell bucket-cell--${
            status === 'mismatch' ? 'mismatch' : status === 'empty' ? 'empty' : 'match'
          }`;
          const clickable = status === 'mismatch' && onSelect;
          return (
            <button
              key={bucketNo}
              type="button"
              className={className}
              title={
                bucket
                  ? `桶 ${bucketNo} · ${status} · 源 ${bucket.src_count}/目标 ${bucket.tgt_count}`
                  : `桶 ${bucketNo} · 未计算`
              }
              onClick={() => clickable && onSelect(bucketNo)}
              style={{
                outline: activeBucket === bucketNo ? '2px solid var(--ink)' : undefined,
                outlineOffset: '1px',
                ...(compact ? { aspectRatio: 'auto', height: 15 } : {}),
              }}
            >
              {status === 'mismatch' ? bucketNo : compact ? '' : bucketNo % 8 === 0 ? bucketNo : ''}
            </button>
          );
        })}
      </div>
      <div className="bucket-legend">
        <span className="m">一致（跳过）</span>
        <span className="x">不一致（已下钻）</span>
        <span className="e">空桶</span>
      </div>
    </div>
  );
}
