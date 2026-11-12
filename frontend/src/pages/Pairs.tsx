/** /pairs 表映射配置：左表右上详情（共用 PairSummaryCard），展示主键与字段比对口径。 */
import { useEffect, useMemo, useState } from 'react';
import { listPairs, updatePair } from '../api/pairs';
import { ErrorNote } from '../components/common/ErrorNote';
import { LedgerTable } from '../components/common/LedgerTable';
import { LoadingRule } from '../components/common/LoadingRule';
import { PairSummaryCard } from '../components/common/PairSummaryCard';
import { FIELD_TYPE_LABELS, PAIR_STATUS_LABELS } from '../constants/enums';
import { useAuthStore } from '../stores/authStore';
import type { Pair } from '../types/models';
import { errorMessage } from '../utils/errorMessage';
import { formatInt } from '../utils/formatNumber';

export function Pairs() {
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const canWrite = useAuthStore((state) => state.can('pairs:write'));
  const user = useAuthStore((state) => state.user);

  const load = () => {
    setLoading(true);
    listPairs()
      .then((data) => {
        setPairs(data.items);
        setSelectedId((current) => current ?? data.items[0]?.id ?? null);
        setError('');
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const selected = useMemo(
    () => pairs.find((pair) => pair.id === selectedId) || pairs[0] || null,
    [pairs, selectedId],
  );
  const totalSrc = pairs.reduce((sum, pair) => sum + pair.row_estimate_src, 0);
  const totalTgt = pairs.reduce((sum, pair) => sum + pair.row_estimate_tgt, 0);

  const toggleStatus = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const next = await updatePair(selected.id, { status: selected.status === 'active' ? 'paused' : 'active' });
      setPairs((current) => current.map((pair) => (pair.id === next.id ? next : pair)));
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const toggleCore = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const next = await updatePair(selected.id, { is_core: !selected.is_core });
      setPairs((current) => current.map((pair) => (pair.id === next.id ? next : pair)));
      setError('');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-head__kicker">Schedule 02 · 表映射</div>
          <h1>表映射与字段口径</h1>
        </div>
        <div className="page-head__meta">
          5 个表对 · 源端 {formatInt(totalSrc)} 行 / 目标端 {formatInt(totalTgt)} 行
          <br />
          当前角色：{user?.role_label || user?.role || '—'}
        </div>
      </header>

      {error ? <ErrorNote message={error} title="读取失败" /> : null}
      {loading ? <LoadingRule label="正在读取表映射…" /> : null}

      <div className="split">
        <section>
          <ul className="list-index">
            {pairs.map((pair, index) => (
              <li key={pair.id}>
                <button
                  type="button"
                  className={`list-index__item ${selected?.id === pair.id ? 'is-active' : ''}`}
                  onClick={() => setSelectedId(pair.id)}
                >
                  <span className="list-index__no">{String(index + 1).padStart(2, '0')}</span>
                  <span>
                    <span className="list-index__title">{pair.display_name}</span>
                    <span className="list-index__meta" style={{ display: 'block' }}>
                      {pair.code} · PK {pair.primary_key}
                    </span>
                  </span>
                  <span className={`mono ${pair.status === 'active' ? 'green' : 'muted'}`} style={{ fontSize: 'var(--step--1)' }}>
                    {PAIR_STATUS_LABELS[pair.status]}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="mono muted" style={{ fontSize: 'var(--step--1)', marginTop: 14 }}>
            源端 REFUND 存在 1 行主键 NULL，参与对账会直接判 null_primary_key。
          </p>
        </section>

        <section>
          {selected ? (
            <>
              <PairSummaryCard pair={selected} />
              <div className="panel">
                <div className="panel__head">
                  <h2 style={{ fontSize: 'var(--step-1)' }}>字段比对口径</h2>
                  <span className="panel__note">
                    共 {selected.field_count} 列 · 主键 {selected.primary_key}
                  </span>
                </div>
                <LedgerTable
                  rows={selected.field_rules}
                  rowKey={(row) => row.name}
                  columns={[
                    {
                      key: 'name',
                      label: '字段',
                      width: '180px',
                      render: (row) => (
                        <span className="mono">
                          {row.name}
                          {row.name === selected.primary_key ? <span className="red"> · PK</span> : null}
                        </span>
                      ),
                    },
                    {
                      key: 'type',
                      label: '归一化类型',
                      width: '120px',
                      render: (row) => <span className="mono">{FIELD_TYPE_LABELS[row.type] || row.type}</span>,
                    },
                    {
                      key: 'compare',
                      label: '比较方式',
                      render: (row) => (
                        <span className="mono muted">
                          {row.type === 'numeric'
                            ? '数值相对误差 |a-b|/max(|a|,1)'
                            : row.type === 'datetime'
                              ? '时间归一化后比较'
                              : '字符串归一化编辑距离'}
                        </span>
                      ),
                    },
                  ]}
                />
              </div>
              {canWrite ? (
                <div className="row">
                  <button className="btn" type="button" onClick={toggleStatus} disabled={saving}>
                    {saving ? '写入中…' : selected.status === 'active' ? '暂停该表对' : '恢复该表对'}
                  </button>
                  <button className="btn btn--ghost" type="button" onClick={toggleCore} disabled={saving}>
                    {selected.is_core ? '取消核心表标记' : '标记为核心表'}
                  </button>
                  <span className="mono muted" style={{ fontSize: 'var(--step--1)' }}>
                    仅迁移负责人（admin）可维护映射；核心表必须被签核批次覆盖，操作写入审计日志。
                  </span>
                </div>
              ) : (
                <div className="empty-state">
                  <strong>只读视图</strong>
                  <div>· 当前角色不能修改表映射与字段口径</div>
                  <div>· 可查看字段规则、行数估计与负责人</div>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <strong>还没有表对</strong>
              <div>· 运行 seed_demo 后会自动注册 5 个迁移表对</div>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
