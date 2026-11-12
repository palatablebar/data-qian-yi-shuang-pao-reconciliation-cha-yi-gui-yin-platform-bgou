/** 页脚页码 + 复核签署位：底稿的页码感。 */
import { useLocation } from 'react-router-dom';

const PAGE_MAP: Record<string, number> = {
  '/pairs': 2,
  '/batches/new': 3,
  '/diffs': 5,
  '/tickets': 6,
};

export function PageFooter() {
  const location = useLocation();
  const base = PAGE_MAP[location.pathname] || (location.pathname.startsWith('/batches/') ? 4 : 1);
  return (
    <footer className="page-footer">
      <span>明川银行 · 数据中台迁移组 · 双跑验收底稿（内部）</span>
      <span>
        — 第 {base} 页 / 共 06 页 — <span className="muted">复核：迁移组 + 审计组</span>
      </span>
    </footer>
  );
}
