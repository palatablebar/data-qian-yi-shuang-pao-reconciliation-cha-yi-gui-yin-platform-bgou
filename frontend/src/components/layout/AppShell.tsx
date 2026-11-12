/** 认证页外壳：窄索引栏 + 主账簿区 + 页脚。 */
import { Outlet } from 'react-router-dom';
import { useAuthGuard } from '../../hooks/useAuthGuard';
import { IndexRail } from './IndexRail';
import { PageFooter } from './PageFooter';

export function AppShell() {
  useAuthGuard();
  return (
    <div className="app-shell">
      <IndexRail />
      <main className="ledger-main">
        <Outlet />
        <PageFooter />
      </main>
    </div>
  );
}
