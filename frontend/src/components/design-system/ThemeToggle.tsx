import React from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { clsx } from 'clsx';

export const ThemeToggle: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const { theme, setTheme } = useTheme();

  const options: { value: 'light' | 'dark' | 'system'; icon: React.ReactNode; label: string }[] = [
    { value: 'light', icon: <Sun className="w-3.5 h-3.5" />, label: 'Light' },
    { value: 'dark', icon: <Moon className="w-3.5 h-3.5" />, label: 'Dark' },
    { value: 'system', icon: <Monitor className="w-3.5 h-3.5" />, label: 'System' },
  ];

  if (compact) {
    const current = options.find(o => o.value === theme) || options[1];
    const next = options[(options.indexOf(current) + 1) % options.length];
    return (
      <button
        onClick={() => setTheme(next.value)}
        className={clsx(
          'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all',
          'bg-slate-800/60 dark:bg-slate-800/60 light:bg-gray-100',
          'text-slate-300 dark:text-slate-300 hover:text-white',
          'border border-slate-700/50 dark:border-slate-700/50 hover:border-cyan-500/50',
          'hover:bg-slate-700/60'
        )}
        title={`Switch to ${next.label} mode`}
      >
        {current.icon}
        <span className="hidden sm:inline">{current.label}</span>
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1 bg-slate-900 dark:bg-slate-900 bg-opacity-80 border border-slate-700 dark:border-slate-700 rounded-lg p-1">
      {options.map(opt => (
        <button
          key={opt.value}
          onClick={() => setTheme(opt.value)}
          className={clsx(
            'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all',
            theme === opt.value
              ? 'bg-cyan-600/20 text-cyan-400 border border-cyan-600/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          )}
          title={`${opt.label} mode`}
        >
          {opt.icon}
          <span>{opt.label}</span>
        </button>
      ))}
    </div>
  );
};
