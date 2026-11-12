export function LoadingRule({ label = '正在核对底稿…' }: { label?: string }) {
  return (
    <div className="empty-state" role="status">
      <strong>{label}</strong>
      <div>· 读取后端对账结果（前端不造数）</div>
    </div>
  );
}
