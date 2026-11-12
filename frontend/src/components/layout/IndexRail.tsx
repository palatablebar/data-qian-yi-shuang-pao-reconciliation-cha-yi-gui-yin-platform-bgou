/** 左侧窄索引栏：审计案卷的目录脊，四个工作台入口。 */
import { NavLink } from 'react-router-dom';
import { CASE_NO } from '../../constants/labels';

const ITEMS = [
  { to: '/pairs', label: '表映射' },
  { to: '/batches/new', label: '发起批次' },
  { to: '/diffs', label: '差异下钻' },
  { to: '/tickets', label: '修复单' },
];

export function IndexRail() {
  return (
    <aside className="index-rail">
      <NavLink to="/pairs" className="index-rail__brand">
        对账底稿
      </NavLink>
      <div className="index-rail__case">{CASE_NO}</div>
      <nav className="index-rail__nav">
        {ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `index-rail__item ${isActive ? 'is-active' : ''}`}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
