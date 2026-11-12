/** 登录守卫：无 token 跳 /login；有 token 时用 /auth/me 校正用户信息。 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { me } from '../api/auth';
import { useAuthStore } from '../stores/authStore';

export function useAuthGuard(): void {
  const navigate = useNavigate();
  const token = useAuthStore((state) => state.token);
  const setUser = useAuthStore((state) => state.setUser);
  const logout = useAuthStore((state) => state.logout);

  useEffect(() => {
    if (!token) {
      navigate('/login', { replace: true });
      return;
    }
    let alive = true;
    me()
      .then((user) => {
        if (alive) setUser(user);
      })
      .catch(() => {
        if (alive) {
          logout();
          navigate('/login', { replace: true });
        }
      });
    return () => {
      alive = false;
    };
  }, [token, navigate, setUser, logout]);
}
