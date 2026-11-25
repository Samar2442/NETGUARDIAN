import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/useAppStore';
import { api } from '../services/api';
import { ThemeToggle } from '../components/design-system/ThemeToggle';
import { Lock, User, AlertCircle } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const loginToStore = useAppStore((state) => state.login);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('NetGuardianAdmin2026!');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await api.login({ username, password });
      loginToStore(res.username, res.role, res.access_token);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col justify-center items-center px-4 relative">
      <div className="absolute top-4 right-4">
        <ThemeToggle compact />
      </div>
      <div className="w-full max-w-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-8 shadow-xl dark:shadow-2xl">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-lg bg-cyan-600 flex items-center justify-center text-white font-mono font-bold text-xl shadow-lg shadow-cyan-900/30 mb-3">
            NG
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">NETGUARDIAN</h1>
          <p className="text-xs font-mono text-cyan-600 dark:text-cyan-400 mt-1 uppercase tracking-widest">
            Detect. Understand. Predict. Recover.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 rounded bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800/80 text-rose-700 dark:text-rose-300 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-mono uppercase text-slate-500 dark:text-slate-400 mb-1">Username</label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3 top-3" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-md py-2.5 pl-9 pr-3 text-sm font-mono text-slate-900 dark:text-slate-100 focus:outline-none focus:border-cyan-500"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono uppercase text-slate-500 dark:text-slate-400 mb-1">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3 top-3" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-md py-2.5 pl-9 pr-3 text-sm font-mono text-slate-900 dark:text-slate-100 focus:outline-none focus:border-cyan-500"
                required
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-semibold py-2.5 rounded-md text-sm transition-colors shadow-lg shadow-cyan-900/20 flex items-center justify-center space-x-2"
            >
              {loading ? <span>Authenticating...</span> : <span>Sign In to NetGuardian</span>}
            </button>
          </div>
        </form>

        <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-800/80 text-center">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Default Lab Credentials: <code className="text-cyan-600 dark:text-cyan-400">admin</code> / <code className="text-cyan-600 dark:text-cyan-400">NetGuardianAdmin2026!</code>
          </p>
          <p className="text-[11px] text-slate-400 mt-1">
            SaturnX Academy Network Operations Center
          </p>
        </div>
      </div>
    </div>
  );
};
