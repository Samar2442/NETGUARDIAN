import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: string;
  color?: 'cyan' | 'emerald' | 'amber' | 'rose' | 'indigo';
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = 'cyan',
}) => {
  const colorMap = {
    cyan: 'text-cyan-400 bg-cyan-950/40 border-cyan-900/40',
    emerald: 'text-emerald-400 bg-emerald-950/40 border-emerald-900/40',
    amber: 'text-amber-400 bg-amber-950/40 border-amber-900/40',
    rose: 'text-rose-400 bg-rose-950/40 border-rose-900/40',
    indigo: 'text-indigo-400 bg-indigo-950/40 border-indigo-900/40',
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4 shadow-sm backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{title}</span>
        <div className={`p-2 rounded-md border ${colorMap[color]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <div className="mt-3 flex items-baseline justify-between">
        <div className="text-2xl font-bold font-mono text-slate-100">{value}</div>
        {trend && (
          <span className="text-xs font-mono text-slate-400">{trend}</span>
        )}
      </div>
      {subtitle && (
        <div className="mt-1 text-xs text-slate-400">{subtitle}</div>
      )}
    </div>
  );
};
