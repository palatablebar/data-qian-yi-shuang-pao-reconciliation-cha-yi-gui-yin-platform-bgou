/** 认证 store：token + 当前用户（localStorage 持久化，刷新不掉登录）。 */
import { create } from 'zustand';
import { clearSession, readCachedUser, readToken, writeSession } from '../api/client';
import type { User } from '../types/models';

interface AuthState {
  token: string | null;
  user: User | null;
  setSession: (token: string, user: User) => void;
  setUser: (user: User) => void;
  logout: () => void;
  can: (action: string) => boolean;
}

const PERMISSIONS: Record<string, string[]> = {
  'pairs:write': ['admin'],
  'batches:create': ['admin', 'analyst'],
  'batches:run': ['admin', 'analyst'],
  'tickets:create': ['admin', 'analyst'],
  'tickets:approve': ['admin'],
  'signoffs:create': ['admin', 'analyst'],
  'signoffs:sign': ['admin'],
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: readToken(),
  user: readCachedUser<User>(),
  setSession: (token, user) => {
    writeSession(token, user);
    set({ token, user });
  },
  setUser: (user) => {
    writeSession(readToken() || '', user);
    set({ user });
  },
  logout: () => {
    clearSession();
    set({ token: null, user: null });
  },
  can: (action) => {
    const role = get().user?.role;
    if (!role) return false;
    return (PERMISSIONS[action] || []).includes(role);
  },
}));
