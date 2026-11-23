import { create } from 'zustand';
import { UserRole } from '../types';

interface AppState {
  isAuthenticated: boolean;
  username: string;
  role: UserRole;
  token: string | null;
  environment: 'LAB-SIMULATION' | 'CISCO-PROD';
  wsConnected: boolean;
  activeNotification: string | null;
  
  // Actions
  login: (username: string, role: UserRole, token: string) => void;
  logout: () => void;
  switchRole: (role: UserRole) => void;
  setEnvironment: (env: 'LAB-SIMULATION' | 'CISCO-PROD') => void;
  setWsConnected: (connected: boolean) => void;
  showNotification: (msg: string) => void;
  clearNotification: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  isAuthenticated: !!localStorage.getItem('netguardian_token'),
  username: localStorage.getItem('netguardian_user') || 'admin',
  role: (localStorage.getItem('netguardian_role') as UserRole) || 'admin',
  token: localStorage.getItem('netguardian_token'),
  environment: 'LAB-SIMULATION',
  wsConnected: false,
  activeNotification: null,

  login: (username, role, token) => {
    localStorage.setItem('netguardian_token', token);
    localStorage.setItem('netguardian_user', username);
    localStorage.setItem('netguardian_role', role);
    set({ isAuthenticated: true, username, role, token });
  },

  logout: () => {
    localStorage.removeItem('netguardian_token');
    localStorage.removeItem('netguardian_user');
    localStorage.removeItem('netguardian_role');
    set({ isAuthenticated: false, username: '', role: 'viewer', token: null });
  },

  switchRole: (role) => {
    localStorage.setItem('netguardian_role', role);
    set({ role });
  },

  setEnvironment: (environment) => set({ environment }),
  setWsConnected: (wsConnected) => set({ wsConnected }),
  showNotification: (activeNotification) => set({ activeNotification }),
  clearNotification: () => set({ activeNotification: null }),
}));
