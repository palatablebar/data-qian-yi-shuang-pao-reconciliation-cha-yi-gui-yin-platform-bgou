/** /batches/new 批次发起：表对多选 + 桶数/抽样率/时间窗 + 实时预估扫描量。 */
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createBatch, estimate } from '../api/batches';
import { listPairs } from '../api/pairs';
import { ErrorNote } from '../components/common/ErrorNote';
import { LoadingRule } from '../components/common/LoadingRule';
import { PairSummaryCard } from '../components/common/PairSummaryCard';
import { StatLedger } from '../components/common/StatLedger';
import { STRATEGY_LABELS } from '../constants/enums';
import { useAuthStore } from '../stores/authStore';
import type { Estimate, Pair } from '../types/models';
import { errorMessage } from '../utils/errorMessage';
import { formatInt, formatMs } from '../utils/formatNumber';

const CORE_CODES = ['orders', 'order_item', 'customer'];

export function BatchNew() {
  const navigate = useNavigate();
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [selected, setSelected] = useState<string[]>(CORE_CODES);
  const [bucketCount, setBucketCount] = useState(128);
  const [sampleRate, setSampleRate] = useState(5);
  const [windowDays, setWindowDays] = useState(30);
  const [strategy, setStrategy] = useState('checksum');
  const [estimateData, setEstimateData] = useState<Estimate | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const canCreate = useAuthStore((state) => state.can('batches:create'));

  useEffect(() => {
    listPairs()
      .then((data) => {
        setPairs(data.items);
        const available = data.items.filter((pair) => pair.status === 'active').map((pair) => pair.code);
        const defaults = CORE_CODES.filter((code) => available.includes(code));
        setSelected(defaults.length > 0 ? defaults : available.slice(0, 1));
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selected.length === 0) {
      setEstimateData(null);
      return;
    }
    let alive = true;
    const timer = window.setTimeout(() => {
      estimate(selected, bucketCount, sampleRate)
        .then((data) => alive && setEstimateData(data))
        .catch(() => undefined);
    }, 220);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [selected, bucketCount, sampleRate]);

  const toggle = (code: string) => {
    setSelected((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    );
  };

  const selectedPairs = useMemo(
    () => pairs.filter((pair) => selected.includes(pair.code)),
    [pairs, selected],
  );

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (selected.length === 0) {
      setError('批次必须至少选择一张表对');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const batch = await createBatch({
        pair_codes: selected,
        strategy,
        bucket_count: bucketCount,
        sample_rate: sampleRate,
        window_days: windowDays,
        note: `Web 发起：${selected.join('/')} ${bucketCount} 桶 / ${sampleRate}% 抽样`,
      });
      navigate(`/batches/${batch.id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-head__kicker">Schedule 03 · 发起批次</div>
          <h1>发起双跑对账批次</h1>
        </div>
        <div className="page-head__meta">
          策略：主键稳定哈希分桶 → 桶级 checksum
          <br />
          一致桶跳过，不一致桶按抽样率下钻
        </div>
      </header>

      {error ? <ErrorNote message={error} title="批次未能创建" /> : null}
      {loading ? <LoadingRule label="正在读取表对…" /> : null}

      <form onSubmit={onSubmit} className="split">
        <section>
          <div className="panel">
            <div className="panel__head">
              <h2 style={{ fontSize: 'var(--step-1)' }}>选择表对</h2>
              <span className="panel__note">本批次先验 3 张核心表；refund 待修 NULL 主键</span>
            </div>
            <ul className="check-list">
              {pairs.map((pair) => (
                <li key={pair.code}>
                  <input
                    id={`pair-${pair.code}`}
                    type="checkbox"
                    checked={selected.includes(pair.code)}
                    onChange={() => toggle(pair.code)}
                    disabled={pair.status !== 'active'}
                  />
                  <label htmlFor={`pair-${pair.code}`} style={{ flex: 1, cursor: 'pointer' }}>
                    <span style={{ fontWeight: 700 }}>{pair.display_name}</span>
                    <span className="mono muted" style={{ fontSize: 'var(--step--1)', marginLeft: 8 }}>
                      {pair.code} · {formatInt(pair.row_estimate_src)} 行
                    </span>
                  </label>
                  {pair.status !== 'active' ? <span className="mono red">已暂停</span> : null}
                </li>
              ))}
            </ul>
          </div>

          <div className="form-grid">
            <div className="field">
              <label htmlFor="strategy">对账策略</label>
              <select id="strategy" value={strategy} onChange={(event) => setStrategy(event.target.value)}>
                <option value="checksum">{STRATEGY_LABELS.checksum}</option>
                <option value="row_hash">{STRATEGY_LABELS.row_hash}</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="buckets">桶数 N</label>
              <select
                id="buckets"
                value={bucketCount}
                onChange={(event) => setBucketCount(Number(event.target.value))}
              >
                {[64, 128, 256].map((value) => (
                  <option value={value} key={value}>
                    {value} 桶
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="sample">抽样率（%）</label>
              <input
                id="sample"
                type="number"
                min={1}
                max={100}
                value={sampleRate}
                onChange={(event) => setSampleRate(Number(event.target.value))}
              />
              <span className="field__hint">不一致桶内按 md5(pk|sample) 确定性抽样</span>
            </div>
            <div className="field">
              <label htmlFor="window">时间窗（天）</label>
              <input
                id="window"
                type="number"
                min={1}
                max={90}
                value={windowDays}
                onChange={(event) => setWindowDays(Number(event.target.value))}
              />
              <span className="field__hint">双跑验收默认回看 30 天</span>
            </div>
          </div>

          <div className="row">
            <button className="btn btn--primary" type="submit" disabled={busy || !canCreate || selected.length === 0}>
              {busy ? '正在建批次…' : '创建批次'}
            </button>
            {!canCreate ? <span className="mono muted">当前角色只读，不能发起批次</span> : null}
          </div>
        </section>

        <section>
          <div className="panel">
            <div className="panel__head">
              <h2 style={{ fontSize: 'var(--step-1)' }}>预估扫描量</h2>
              <span className="panel__note">由后端按历史批次均速估算</span>
            </div>
            {estimateData ? (
              <StatLedger
                cells={[
                  { label: '表对', value: `${estimateData.pair_count} 张`, hint: selected.join(' / ') },
                  { label: '源/目标行', value: `${formatInt(estimateData.src_rows)}`, hint: `目标 ${formatInt(estimateData.tgt_rows)}` },
                  { label: '桶数', value: `${estimateData.bucket_count}`, hint: `每桶约 ${formatInt(estimateData.rows_per_bucket)} 行` },
                  { label: '预计抽样行', value: `${formatInt(estimateData.estimated_sampled_rows)}`, hint: `${estimateData.sample_rate}% 抽样` },
                  {
                    label: '预估耗时',
                    value: estimateData.estimated_scan_ms > 0 ? formatMs(estimateData.estimated_scan_ms) : '—',
                    hint: estimateData.source_batch ? `历史基准 ${estimateData.source_batch}` : '首跑后按均速估算',
                  },
                ]}
              />
            ) : (
              <div className="empty-state">
                <strong>选择表对后给出预估</strong>
                <div>· 行数来自表映射维护的统计值</div>
                <div>· 耗时为 桶数 × 历史单桶平均耗时</div>
              </div>
            )}
            <p className="mono muted" style={{ fontSize: 'var(--step--1)', lineHeight: 2 }}>
              桶号 = int(md5(pk)[:8], 16) mod N；桶级 checksum = Σ int(h[:8], 16) mod 2^32；
              行级 h = md5(各列规范化值用 | 连接)。一致桶直接跳过，不一致桶才抽样下钻。
            </p>
          </div>

          {selectedPairs.map((pair) => (
            <PairSummaryCard pair={pair} key={pair.code} compact />
          ))}
        </section>
      </form>
    </>
  );
}
