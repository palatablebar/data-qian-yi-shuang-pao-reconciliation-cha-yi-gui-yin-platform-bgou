/** /signoffs 签核底稿：选已完成批次冻结结论、签核、重签与材料过期提示。 */
import { useEffect, useMemo, useState } from 'react';
import { listBatches } from '../api/batches';
import {
  createSignoff,
  exportSignoff,
  listSignoffs,
  refreshSignoff,
  resignSignoff,
  signSignoff,
} from '../api/signoffs';
import { ErrorNote } from '../components/common/ErrorNote';
import { LedgerTable } from '../components/common/LedgerTable';
import { LoadingRule } from '../components/common/LoadingRule';
import { StatusSeal } from '../components/common/StatusSeal';
import { DIFF_TYPE_LABELS, SIGNOFF_FRESHNESS_LABELS, SIGNOFF_STATUS_LABELS, STALE_REASON_LABELS } from '../constants/enums';
import { useAuthStore } from '../stores/authStore';
import type { Batch, Signoff } from '../types/models';
import { errorMessage } from '../utils/errorMessage';
import { formatInt } from '../utils/formatNumber';
import { formatTime } from '../utils/formatTime';

export function Signoffs() {
  const [signoffs, setSignoffs] = useState<Signoff[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [title, setTitle] = useState('上线评审验收底稿');
  const [note, setNote] = useState('阻塞差异清零、核心表全覆盖后由迁移负责人签核。');
  const [signNote, setSignNote] = useState('核对冻结快照与修复单，同意作为上线验收结论。');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const canCreate = useAuthStore((state) => state.can('signoffs:create'));
  const canSign = useAuthStore((state) => state.can('signoffs:sign'));

  const load = () => {
    listSignoffs()
      .then((data) => {
        setSignoffs(data.items);
        setSelectedId((current) => current ?? data.items[0]?.id ?? null);
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    listBatches()
      .then((data) => {
        setBatches(data.items);
        const firstCompleted = data.items.find((batch) => batch.status === 'completed');
        if (firstCompleted) setSelectedIds([firstCompleted.id]);
      })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const selected = useMemo(
    () => signoffs.find((item) => item.id === selectedId) || signoffs[0] || null,
    [signoffs, selectedId],
  );
  const completedBatches = useMemo(() => batches.filter((batch) => batch.status === 'completed'), [batches]);

  const toggleBatch = (id: number) => {
    setSelectedIds((current) => (current.includes(id) ? current.filter((v) => v !== id) : [...current, id]));
  };

  const runAction = async (promise: Promise<unknown>, message: string) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await promise;
      setNotice(message);
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const onCreate = () => {
    if (selectedIds.length === 0) {
      setError('先至少选择一个已完成批次');
      return;
    }
    return runAction(
      createSignoff({ batch_ids: selectedIds, title, note }),
      '已生成冻结底稿草稿（相同批次组合不会重复建档）',
    );
  };

  const snapshot = selected?.snapshot_json;
  const validation = selected?.validation_json;
  const freshness = selected?.freshness;
  const isStale = freshness?.freshness === 'stale';

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-head__kicker">Schedule 07 · 签核底稿</div>
          <h1>上线验收签核底稿</h1>
        </div>
        <div className="page-head__meta">
          冻结记录列明可验收表、阻塞差异与已准确豁免差异
          <br />
          已签记录不被改写；材料过期会提示重签
        </div>
      </header>

      {error ? <ErrorNote message={error} title="操作未通过" /> : null}
      {notice ? (
        <div className="error-note" style={{ borderLeftColor: 'var(--stamp-green)' }}>
          <strong style={{ color: 'var(--stamp-green)' }}>已记录</strong>
          <div>{notice}</div>
        </div>
      ) : null}

      <div className="split">
        <section>
          <div className="panel">
            <div className="panel__head">
              <h2 style={{ fontSize: 'var(--step-1)' }}>选择批次生成冻结记录</h2>
              <span className="panel__note">仅已完成批次可选</span>
            </div>
            <ul className="list-index">
              {completedBatches.map((batch) => (
                <li key={batch.id}>
                  <button
                    type="button"
                    className="list-index__item"
                    style={{
                      boxShadow: selectedIds.includes(batch.id) ? 'inset 2px 0 0 var(--vermillion)' : undefined,
                      background: selectedIds.includes(batch.id) ? 'var(--paper-deep)' : undefined,
                    }}
                    onClick={() => toggleBatch(batch.id)}
                  >
                    <span className="list-index__no mono">{selectedIds.includes(batch.id) ? '✓' : '○'}</span>
                    <span>
                      <span className="list-index__title mono">{batch.batch_no}</span>
                      <span className="list-index__meta" style={{ display: 'block' }}>
                        {batch.pair_codes.join(' / ')} · 差异 {formatInt(batch.diff_count)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
              {completedBatches.length === 0 ? <li className="empty-state">暂无已完成批次</li> : null}
            </ul>
            <div className="field" style={{ marginTop: 14 }}>
              <label htmlFor="signoff-title">底稿标题</label>
              <input id="signoff-title" value={title} maxLength={160} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="signoff-note">备注</label>
              <textarea id="signoff-note" rows={2} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
            </div>
            <button className="btn btn--primary" type="button" disabled={busy || !canCreate} onClick={onCreate}>
              {busy ? '处理中…' : '生成/复用冻结草稿'}
            </button>
            {!canCreate ? <div className="mono muted" style={{ marginTop: 8, fontSize: 'var(--step--1)' }}>当前角色只读</div> : null}
          </div>

          <div className="panel">
            <div className="panel__head">
              <h2 style={{ fontSize: 'var(--step-1)' }}>签核台账</h2>
              <span className="panel__note">共 {signoffs.length} 份</span>
            </div>
            {loading ? (
              <LoadingRule label="正在读取签核底稿…" />
            ) : (
              <LedgerTable<Signoff>
                rows={signoffs}
                rowKey={(row) => row.id}
                emptyHint="还没有签核底稿：在上方选择批次生成。"
                columns={[
                  {
                    key: 'no',
                    label: '编号',
                    width: '150px',
                    render: (row) => (
                      <button
                        type="button"
                        className="mono"
                        style={{ textDecoration: 'underline', background: 'none', border: 0, cursor: 'pointer' }}
                        onClick={() => setSelectedId(row.id)}
                      >
                        {row.signoff_no}
                      </button>
                    ),
                  },
                  {
                    key: 'title',
                    label: '内容',
                    render: (row) => (
                      <div>
                        <div>{row.title}</div>
                        <div className="mono muted" style={{ fontSize: 'var(--step--1)' }}>
                          批次 {row.batch_ids.join(' / ')}
                        </div>
                      </div>
                    ),
                  },
                  {
                    key: 'status',
                    label: '状态',
                    width: '96px',
                    render: (row) => (
                      <StatusSeal
                        status={row.status}
                        label={SIGNOFF_STATUS_LABELS[row.status] || row.status}
                        tone={row.status === 'signed' ? 'green' : 'muted'}
                      />
                    ),
                  },
                  {
                    key: 'freshness',
                    label: '材料',
                    width: '110px',
                    render: (row) => {
                      const fresh = row.freshness?.freshness;
                      return (
                        <StatusSeal
                          status={fresh === 'stale' ? 'failed' : 'completed'}
                          label={fresh ? SIGNOFF_FRESHNESS_LABELS[fresh] : '—'}
                          tone={fresh === 'stale' ? 'red' : fresh === 'fresh' ? 'green' : 'muted'}
                        />
                      );
                    },
                  },
                ]}
              />
            )}
          </div>
        </section>

        <section>
          {!selected ? (
            <div className="empty-state">
              <strong>选择左侧一份底稿查看冻结结论</strong>
            </div>
          ) : (
            <>
              <div className="panel">
                <div className="panel__head">
                  <h2 style={{ fontSize: 'var(--step-1)' }}>
                    {selected.signoff_no} · {selected.title}
                  </h2>
                  <span className="panel__note">冻结于 {formatTime(snapshot?.frozen_at)}</span>
                </div>

                {isStale ? (
                  <ErrorNote
                    title="材料已过期，需重签"
                    message={(freshness?.stale_reasons || [])
                      .map((reason) => `· ${reason.label || STALE_REASON_LABELS[reason.reason] || reason.reason}`)
                      .join('\n')}
                  />
                ) : (
                  <p className="mono" style={{ color: 'var(--stamp-green)', fontSize: 'var(--step--1)' }}>
                    材料有效：冻结快照与当前批次/修复单一致（{formatTime(freshness?.evaluated_at)} 实时校验）
                  </p>
                )}

                <div className="row" style={{ gap: 8, flexWrap: 'wrap', margin: '10px 0' }}>
                  {selected.status === 'draft' && canCreate ? (
                    <button
                      className="btn btn--ghost"
                      type="button"
                      disabled={busy}
                      onClick={() => runAction(refreshSignoff(selected.id), '草稿已按当前材料重新冻结')}
                    >
                      刷新快照
                    </button>
                  ) : null}
                  {selected.status === 'draft' && canSign ? (
                    <button
                      className="btn btn--primary"
                      type="button"
                      disabled={busy || !validation?.passable}
                      title={validation?.passable ? '' : '核心表未覆盖或仍有未豁免差异'}
                      onClick={() => runAction(signSignoff(selected.id, signNote), '签核通过：结论已冻结，后续变化不改写本记录')}
                    >
                      签核通过
                    </button>
                  ) : null}
                  {selected.status === 'signed' && canCreate ? (
                    <button
                      className="btn"
                      type="button"
                      disabled={busy}
                      onClick={() => runAction(resignSignoff(selected.id), '已基于原记录生成重签草稿，原签核记录保留留痕')}
                    >
                      发起重签（保留原记录）
                    </button>
                  ) : null}
                  <button
                    className="btn btn--ghost"
                    type="button"
                    onClick={() => exportSignoff(selected.id).catch((err) => setError(errorMessage(err)))}
                  >
                    导出底稿 CSV
                  </button>
                </div>

                {selected.status === 'draft' && canSign ? (
                  <div className="field">
                    <label htmlFor="sign-note">签核意见</label>
                    <textarea id="sign-note" rows={2} value={signNote} maxLength={2000} onChange={(e) => setSignNote(e.target.value)} />
                  </div>
                ) : null}

                {validation && !validation.passable ? (
                  <ErrorNote
                    title="当前不能通过签核"
                    message={[
                      validation.uncovered_core_pairs.length
                        ? `· 核心表未覆盖：${validation.uncovered_core_pairs.join(' / ')}`
                        : '',
                      validation.blocking_diff_count ? `· 未豁免差异 ${validation.blocking_diff_count} 条（见下方阻塞清单）` : '',
                    ]
                      .filter(Boolean)
                      .join('\n')}
                  />
                ) : null}
                {selected.status === 'signed' ? (
                  <p className="mono muted" style={{ fontSize: 'var(--step--1)' }}>
                    签核时间 {formatTime(selected.signed_at)} · 意见：{selected.sign_note || '—'}
                  </p>
                ) : null}
              </div>

              <div className="panel">
                <div className="panel__head">
                  <h2 style={{ fontSize: 'var(--step-1)' }}>表对验收结论</h2>
                  <span className="panel__note">
                    核心表 {snapshot?.core_pair_codes.length || 0} 张 · 已覆盖 {snapshot?.covered_pair_codes.length || 0} 张
                  </span>
                </div>
                <LedgerTable
                  rows={snapshot?.pair_verdicts || []}
                  rowKey={(row) => row.pair_code}
                  columns={[
                    {
                      key: 'pair',
                      label: '表对',
                      render: (row) => (
                        <span className="mono">
                          {row.pair_code}
                          {row.is_core ? <strong className="red"> · 核心</strong> : null}
                        </span>
                      ),
                    },
                    {
                      key: 'verdict',
                      label: '结论',
                      width: '100px',
                      render: (row) => (
                        <StatusSeal
                          status={row.verdict === 'acceptable' ? 'completed' : 'failed'}
                          label={row.verdict === 'acceptable' ? '可验收' : '阻塞'}
                          tone={row.verdict === 'acceptable' ? 'green' : 'red'}
                        />
                      ),
                    },
                    { key: 'diff', label: '差异总数', width: '90px', align: 'right', render: (row) => formatInt(row.diff_total) },
                    { key: 'exempt', label: '已豁免', width: '90px', align: 'right', render: (row) => formatInt(row.exempted_count) },
                    { key: 'block', label: '阻塞', width: '90px', align: 'right', render: (row) => formatInt(row.blocking_count) },
                  ]}
                />
              </div>

              <div className="panel">
                <div className="panel__head">
                  <h2 style={{ fontSize: 'var(--step-1)' }}>已准确豁免的差异（已审批修复单）</h2>
                  <span className="panel__note">共 {snapshot?.exemptions.length || 0} 张修复单</span>
                </div>
                <LedgerTable
                  rows={snapshot?.exemptions || []}
                  rowKey={(row) => row.ticket_id}
                  emptyHint="暂无已审批修复单覆盖的差异。"
                  columns={[
                    { key: 'no', label: '修复单', width: '170px', render: (row) => <span className="mono">{row.ticket_no}</span> },
                    {
                      key: 'title',
                      label: '内容',
                      render: (row) => (
                        <div>
                          <div>{row.title}</div>
                          <div className="mono muted" style={{ fontSize: 'var(--step--1)' }}>
                            {Object.entries(row.by_type || {})
                              .map(([type, count]) => `${DIFF_TYPE_LABELS[type] || type} ${count}`)
                              .join(' / ')}
                          </div>
                        </div>
                      ),
                    },
                    { key: 'count', label: '豁免行数', width: '90px', align: 'right', render: (row) => formatInt(row.exempted_diff_count) },
                    {
                      key: 'decided',
                      label: '审批时间',
                      width: '150px',
                      render: (row) => <span className="mono muted" style={{ fontSize: 'var(--step--1)' }}>{formatTime(row.decided_at)}</span>,
                    },
                  ]}
                />
              </div>

              <div className="panel">
                <div className="panel__head">
                  <h2 style={{ fontSize: 'var(--step-1)' }}>阻塞差异（未豁免）</h2>
                  <span className="panel__note">{validation?.blocking_diff_count ?? 0} 条</span>
                </div>
                <LedgerTable
                  rows={snapshot?.blocking_diffs || []}
                  rowKey={(row) => row.diff_id}
                  emptyHint="没有阻塞差异：全部差异均已被已审批修复单准确豁免。"
                  columns={[
                    { key: 'id', label: '差异ID', width: '80px', render: (row) => <span className="mono">{row.diff_id}</span> },
                    { key: 'pair', label: '表对', width: '110px', render: (row) => <span className="mono">{row.pair_code}</span> },
                    {
                      key: 'field',
                      label: '字段/类型',
                      render: (row) => (
                        <span className="mono">
                          {row.field_name} · {DIFF_TYPE_LABELS[row.diff_type] || row.diff_type}
                        </span>
                      ),
                    },
                    { key: 'pk', label: '主键', render: (row) => <span className="mono muted">{row.primary_key_value}</span> },
                    { key: 'bucket', label: '桶号', width: '70px', align: 'right', render: (row) => formatInt(row.bucket_no) },
                  ]}
                />
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}
