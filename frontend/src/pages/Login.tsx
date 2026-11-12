/** 登录页：审计底稿封面（案卷号 + 迁移组抬头 + 三账号说明，手输登录）。 */
import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/auth';
import { ErrorNote } from '../components/common/ErrorNote';
import { APP_SUBTITLE, APP_TITLE, CASE_NO } from '../constants/labels';
import { useAuthStore } from '../stores/authStore';
import { errorMessage } from '../utils/errorMessage';

const DEMO_ACCOUNTS = [
  ['admin@paritycheck.demo', '迁移负责人 · 全部写 + 审批'],
  ['analyst@paritycheck.demo', '数据开发 · 发起批次/提修复单'],
  ['viewer@paritycheck.demo', '审计 · 只读 + 导出'],
];

export function Login() {
  const navigate = useNavigate();
  const setSession = useAuthStore((state) => state.setSession);
  const token = useAuthStore((state) => state.token);
  const [email, setEmail] = useState('admin@paritycheck.demo');
  const [password, setPassword] = useState('Demo@2026');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (token) navigate('/pairs', { replace: true });
  }, [token, navigate]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await login(email.trim(), password);
      setSession(result.access_token, result.user);
      navigate('/pairs', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-stage">
      <section className="login-mast">
        <div>
          <div className="login-mast__case">{CASE_NO}</div>
          <h1>
            数据迁移
            <br />
            双跑对账底稿
          </h1>
          <p className="login-mast__lede">
            明川银行 12 张核心表从 Oracle 19c 迁往 MySQL 8.0。双跑 30 天，按主键稳定分桶 + 行级规范化
            checksum 全量核对，只把不一致的桶抽样下钻——数据工程组的验收底稿，不再靠抽样 SQL 和 Excel。
          </p>
          <hr className="login-mast__rule" />
          <div className="mono muted" style={{ fontSize: 'var(--step--1)', lineHeight: 2 }}>
            源库 → 双写 → 目标库 · 5 个表对 / 12,000 行演示快照 · 对账口径可复现
          </div>
        </div>
        <div className="login-mast__facts">
          <div className="login-mast__fact">
            <b>128 桶</b>核心表批次默认粒度
          </div>
          <div className="login-mast__fact">
            <b>5%</b>不一致桶抽样下钻率
          </div>
          <div className="login-mast__fact">
            <b>2 算法</b>分桶 checksum + 差异归因
          </div>
        </div>
      </section>

      <section className="login-form-wrap">
        <div className="mono red" style={{ letterSpacing: '0.24em', fontSize: 'var(--step--1)' }}>
          {APP_SUBTITLE}
        </div>
        <h2>登录对账台</h2>
        <p>
          使用迁移组账号进入底稿。
          <br />
          三种角色看到的写操作权限不同。
        </p>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="email">迁移组邮箱</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">口令</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          <button className="btn btn--primary" type="submit" disabled={busy} style={{ width: '100%' }}>
            {busy ? '核验登录中…' : '进入底稿'}
          </button>
        </form>
        <ErrorNote message={error} title="登录失败" />
        <div className="login-hint">
          <div>
            <b>演示账号</b>（口令统一 Demo@2026）
          </div>
          {DEMO_ACCOUNTS.map(([account, role]) => (
            <div key={account}>
              <b>{account}</b> · {role}
            </div>
          ))}
        </div>
        <div className="mono muted" style={{ fontSize: 'var(--step--1)', marginTop: 18 }}>
          {APP_TITLE}
        </div>
      </section>
    </div>
  );
}
