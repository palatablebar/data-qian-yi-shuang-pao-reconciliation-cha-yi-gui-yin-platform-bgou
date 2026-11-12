/** /tickets 修复单与验收导出：从批次差异生成修复单、提交、审批、导出底稿 CSV。 */
import { FormEvent, useEffect, useState } from 'react';
import { exportAttribution, listBatches } from '../api/batches';
import { exportDiffs, listDiffs } from '../api/diffs';
import { approveTicket, createTicket, listTickets, rejectTicket, submitTicket } from '../api/tickets';
import { ErrorNote } from '../components/common/ErrorNote';
import { LedgerTable } from '../components/common/LedgerTable';
import { LoadingRule } from '../components/common/LoadingRule';
import { StatusSeal } from '../components/common/StatusSeal';
import { DIFF_TYPE_LABELS, TICKET_STATUS_LABELS } from '../constants/enums';
import { useAuthStore } from '../stores/authStore';
import type { Batch, Ticket } from '../types/models';
import { errorMessage } from '../utils/errorMessage';
import { formatInt } from '../utils/formatNumber';
import { formatTime } from '../utils/formatTime';

export function Tickets() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [title, setTitle] = useState('按批次差异生成修复单');
  const [note, setNote] = useState('按差异分类修复后重跑对应桶。');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const canCreate = useAuthStore((state) => state.can('tickets:create'));
  const canApprove = useAuthStore((state) => state.can('tickets:approve'));

  const loadTickets = () => {
    listTickets()
      .then((data) => setTickets(data.items))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTickets();
    listBatches()
      .then((data) => {
        setBatches(data.items);
        const completed = data.items.find((batch) => batch.status === 'completed');
        setBatchId((current) => current ?? completed?.id ?? data.items[0]?.id ?? null);
      })
      .catch(() => undefined);
  }, []);

  const act = async (promise: Promise<unknown>, message: string) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await promise;
      setNotice(message);
      loadTickets();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const onCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!batchId) {
      setError('先选择一个已完成批次');
      return;
    }
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const diffs = await listDiffs({ batch_id: batchId, limit: 200 });
      if (diffs.items.length === 0) throw new Error('该批次没有差异行，无需修复单');
      const pairCodes = Array.from(new Set(diffs.items.map((diff) => diff.pair_code)));
      await createTicket({
        batch_id: batchId,
        pair_codes: pairCodes,
        diff_ids: diffs.items.map((diff) => diff.id),
        title,
        note,
      });
      setNotice(`已按批次 ${batchId} 的 ${diffs.items.length} 行差异生成草稿修复单`);
      loadTickets();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const selectedBatch = batches.find((batch) => batch.id === batchId) || null;

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-head__kicker">Schedule 06 · 修复单与验收导出</div>
          <h1>修复单与验收底稿</h1>
        </div>
        <div className="page-head__meta">
          {canApprove ? '迁移负责人可审批修复单' : '当前角色只能提交/查看，审批会被拒绝（403）'}
          <br />
          viewer 只读，可导出 CSV 底稿
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
              <h2 style={{ fontSize: 'var(--step-1)' }}>从批次差异生成修复单</h2>
              <span className="panel__note">差异范围由后端汇总（表对/字段/分类）</span>
            </div>
            <form onSubmit={onCreate}>
              <div className="field">
                <label htmlFor="batch">批次</label>
                <select
                  id="batch"
                  value={batchId ?? ''}
                  onChange={(event) => setBatchId(Number(event.target.value))}
                >
                  {batches.map((batch) => (
                    <option key={batch.id} value={batch.id}>
                      {batch.batch_no} · {batch.status} · 差异 {batch.diff_count}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="title">修复单标题</label>
                <input id="title" value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="note">备注</label>
                <textarea id="note" rows={3} value={note} maxLength={2000} onChange={(event) => setNote(event.target.value)} />
              </div>
              <button className="btn btn--primary" type="submit" disabled={busy || !canCreate}>
                {busy ? '生成中…' : '生成草稿修复单'}
              </button>
              {!canCreate ? <div className="mono muted" style={{ marginTop: 8 }}>当前角色只读，不能创建修复单</div> : null}
            </form>
          </div>

          <div className="panel">
            <div className="panel__head">
              <h2 style={{ fontSize: 'var(--step-1)' }}>验收导出</h2>
              <span className="panel__note">HTTP 下载 · UTF-8 BOM CSV</span>
            </div>
            <div className="row">
              <button
                className="btn btn--ghost"
                type="button"
                disabled={!selectedBatch}
                onClick={() =>
                  selectedBatch &&
                  exportDiffs(selectedBatch.id).catch((err) => setError(errorMessage(err)))
                }
              >
                导出差异明细 CSV
              </button>
              <button
                className="btn btn--ghost"
                type="button"
                disabled={!selectedBatch}
                onClick={() =>
                  selectedBatch &&
                  exportAttribution(selectedBatch.id).catch((err) => setError(errorMessage(err)))
                }
              >
                导出归因汇总 CSV
              </button>
            </div>
            <p className="mono muted" style={{ fontSize: 'var(--step--1)', marginTop: 10 }}>
              审计角色（viewer）可导出，但写操作一律 403。
            </p>
          </div>
        </section>

        <section>
          <div className="panel">
            <div className="panel__head">
              <h2 style={{ fontSize: 'var(--step-1)' }}>修复单台账</h2>
              <span className="panel__note">共 {tickets.length} 张</span>
            </div>
            {loading ? (
              <LoadingRule label="正在读取修复单…" />
            ) : (
              <LedgerTable<Ticket>
                rows={tickets}
                rowKey={(row) => row.id}
                emptyHint="还没有修复单：可在左侧从批次差异生成。"
                columns={[
                  {
                    key: 'no',
                    label: '单号',
                    width: '150px',
                    render: (row) => <span className="mono">{row.ticket_no}</span>,
                  },
                  {
                    key: 'title',
                    label: '内容',
                    render: (row) => (
                      <div>
                        <div>{row.title}</div>
                        <div className="mono muted" style={{ fontSize: 'var(--step--1)' }}>
                          {row.pair_codes.join(' / ')} · {formatInt(row.diff_count)} 行 ·{' '}
                          {Object.entries(row.diff_scope_json?.by_type || {})
                            .map(([type, count]) => `${DIFF_TYPE_LABELS[type] || type} ${count}`)
                            .join(' / ')}
                        </div>
                      </div>
                    ),
                  },
                  {
                    key: 'status',
                    label: '状态',
                    width: '92px',
                    render: (row) => (
                      <StatusSeal
                        status={row.status}
                        label={TICKET_STATUS_LABELS[row.status] || row.status}
                        tone={row.status === 'approved' ? 'green' : row.status === 'draft' ? 'muted' : 'red'}
                      />
                    ),
                  },
                  {
                    key: 'time',
                    label: '提交/审批',
                    width: '150px',
                    render: (row) => (
                      <span className="mono muted" style={{ fontSize: 'var(--step--1)' }}>
                        提交 {formatTime(row.submitted_at)}
                        <br />
                        审批 {formatTime(row.decided_at)}
                      </span>
                    ),
                  },
                  {
                    key: 'actions',
                    label: '动作',
                    width: '168px',
                    render: (row) => (
                      <div className="row" style={{ gap: 6 }}>
                        {row.status === 'draft' && canCreate ? (
                          <button
                            className="btn btn--ghost"
                            type="button"
                            disabled={busy}
                            onClick={() => act(submitTicket(row.id), `已提交 ${row.ticket_no} 待审批`)}
                          >
                            提交
                          </button>
                        ) : null}
                        {row.status === 'submitted' && canApprove ? (
                          <>
                            <button
                              className="btn"
                              type="button"
                              disabled={busy}
                              onClick={() => act(approveTicket(row.id, '同意修复'), `已审批通过 ${row.ticket_no}`)}
                            >
                              通过
                            </button>
                            <button
                              className="btn btn--ghost"
                              type="button"
                              disabled={busy}
                              onClick={() => act(rejectTicket(row.id, '退回补充证据'), `已驳回 ${row.ticket_no}`)}
                            >
                              驳回
                            </button>
                          </>
                        ) : null}
                        {row.status === 'submitted' && !canApprove ? (
                          <span className="mono muted" style={{ fontSize: 'var(--step--1)' }}>
                            等待负责人
                          </span>
                        ) : null}
                      </div>
                    ),
                  },
                ]}
              />
            )}
          </div>
        </section>
      </div>
    </>
  );
}
