/** “已核”印章：审计底稿的签署感，按状态换色。 */
interface Props {
  status: string;
  label?: string;
  tone?: 'red' | 'green' | 'muted';
}

const TONE: Record<string, string> = {
  completed: 'green',
  approved: 'green',
  match: 'green',
  failed: 'red',
  mismatch: 'red',
  rejected: 'red',
  running: 'red',
  submitted: 'red',
  pending: 'muted',
  draft: 'muted',
  empty: 'muted',
};

export function StatusSeal({ status, label, tone }: Props) {
  const resolved = tone || TONE[status] || 'muted';
  const className = resolved === 'muted' ? 'stamp stamp--muted' : resolved === 'green' ? 'stamp stamp--green' : 'stamp';
  return <span className={className}>{label || status}</span>;
}
