import React from 'react';
import { clsx } from 'clsx';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumbs?: { label: string; href?: string }[];
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  badge,
  actions,
  breadcrumbs,
}) => {
  return (
    <div className="mb-6">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <div className="flex items-center gap-1.5 mb-2 text-xs font-mono text-text-secondary">
          {breadcrumbs.map((crumb, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="text-text-muted">/</span>}
              <span className={i === breadcrumbs.length - 1 ? 'text-accent' : ''}>{crumb.label}</span>
            </React.Fragment>
          ))}
        </div>
      )}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-text-primary tracking-tight">{title}</h1>
              {badge}
            </div>
            {subtitle && (
              <p className="mt-0.5 text-sm text-text-secondary">{subtitle}</p>
            )}
          </div>
        </div>
        {actions && (
          <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>
        )}
      </div>
    </div>
  );
};

interface StatusBadgeProps {
  status: 'online' | 'offline' | 'degraded' | 'unknown' | 'warning' | 'critical';
  label?: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, size = 'md' }) => {
  const configs = {
    online: { dot: 'bg-emerald-400', text: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-950/40', border: 'border-emerald-200 dark:border-emerald-800/60', label: 'ONLINE' },
    offline: { dot: 'bg-red-400', text: 'text-red-600 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-950/40', border: 'border-red-200 dark:border-red-800/60', label: 'OFFLINE' },
    degraded: { dot: 'bg-amber-400', text: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/40', border: 'border-amber-200 dark:border-amber-800/60', label: 'DEGRADED' },
    unknown: { dot: 'bg-slate-400', text: 'text-slate-600 dark:text-slate-400', bg: 'bg-slate-50 dark:bg-slate-800/40', border: 'border-slate-200 dark:border-slate-700/60', label: 'UNKNOWN' },
    warning: { dot: 'bg-orange-400', text: 'text-orange-600 dark:text-orange-400', bg: 'bg-orange-50 dark:bg-orange-950/40', border: 'border-orange-200 dark:border-orange-800/60', label: 'WARNING' },
    critical: { dot: 'bg-red-500', text: 'text-red-700 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-950/40', border: 'border-red-200 dark:border-red-800/60', label: 'CRITICAL' },
  };

  const c = configs[status];
  const display = label ?? c.label;

  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 font-mono font-semibold border rounded',
      c.text, c.bg, c.border,
      size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-[11px] px-2 py-0.5'
    )}>
      <span className={clsx('rounded-full flex-shrink-0', c.dot, size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2')} />
      {display}
    </span>
  );
};

interface EnvironmentBadgeProps {
  env: string;
}

export const EnvironmentBadge: React.FC<EnvironmentBadgeProps> = ({ env }) => {
  const isSimulation = env.includes('SIMULATION') || env.includes('LAB');
  const isProd = env.includes('PROD') || env.includes('LIVE');

  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 text-[10px] font-mono font-bold px-2 py-0.5 rounded border uppercase tracking-wider',
      isSimulation && 'bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800/60',
      isProd && 'bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 border-red-200 dark:border-red-800/60',
      !isSimulation && !isProd && 'bg-slate-50 dark:bg-slate-800/40 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
    )}>
      {isSimulation ? '⬡' : isProd ? '◈' : '○'} {env}
    </span>
  );
};

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon?: React.ReactNode;
  trend?: { value: number; label?: string };
  status?: 'normal' | 'warning' | 'critical';
  badge?: string;
  subtitle?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  icon,
  trend,
  status = 'normal',
  badge,
  subtitle,
}) => {
  const statusColors = {
    normal: 'border-slate-200 dark:border-slate-800',
    warning: 'border-amber-300 dark:border-amber-700/60',
    critical: 'border-red-300 dark:border-red-700/60',
  };

  const trendColors = trend
    ? trend.value > 0
      ? 'text-red-500 dark:text-red-400'
      : trend.value < 0
      ? 'text-emerald-500 dark:text-emerald-400'
      : 'text-slate-400'
    : '';

  return (
    <div className={clsx(
      'bg-white dark:bg-slate-900 rounded-lg border p-4 flex flex-col gap-3',
      statusColors[status],
      status === 'critical' && 'shadow-sm shadow-red-500/10',
      status === 'warning' && 'shadow-sm shadow-amber-500/10',
    )}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">{title}</span>
        {icon && <span className="text-text-muted">{icon}</span>}
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-bold text-text-primary font-mono tabular-nums">{value}</span>
        {unit && <span className="text-sm text-text-secondary mb-0.5">{unit}</span>}
      </div>
      <div className="flex items-center justify-between">
        {subtitle && <span className="text-xs text-text-muted">{subtitle}</span>}
        {trend && (
          <span className={clsx('text-xs font-mono font-medium', trendColors)}>
            {trend.value > 0 ? '↑' : trend.value < 0 ? '↓' : '→'} {Math.abs(trend.value)}%
            {trend.label && <span className="text-text-muted ml-1">{trend.label}</span>}
          </span>
        )}
        {badge && (
          <span className="text-[10px] font-mono text-text-muted">{badge}</span>
        )}
      </div>
    </div>
  );
};

export const LoadingSkeleton: React.FC<{ className?: string }> = ({ className }) => (
  <div className={clsx('animate-pulse rounded bg-slate-200 dark:bg-slate-800', className)} />
);

export const EmptyState: React.FC<{
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}> = ({ icon, title, description, action }) => (
  <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
    {icon && <div className="text-text-muted mb-2">{icon}</div>}
    <h3 className="text-base font-semibold text-text-primary">{title}</h3>
    {description && <p className="text-sm text-text-secondary max-w-md">{description}</p>}
    {action && <div className="mt-2">{action}</div>}
  </div>
);

export const AlertBanner: React.FC<{
  type: 'info' | 'warning' | 'error' | 'success';
  title?: string;
  message: string;
  onDismiss?: () => void;
}> = ({ type, title, message, onDismiss }) => {
  const styles = {
    info: 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800/60 text-blue-700 dark:text-blue-300',
    warning: 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/60 text-amber-700 dark:text-amber-300',
    error: 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800/60 text-red-700 dark:text-red-300',
    success: 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800/60 text-emerald-700 dark:text-emerald-300',
  };
  return (
    <div className={clsx('border rounded-lg px-4 py-3 text-sm flex items-start justify-between gap-3', styles[type])}>
      <div>
        {title && <div className="font-semibold mb-0.5">{title}</div>}
        <div>{message}</div>
      </div>
      {onDismiss && (
        <button onClick={onDismiss} className="flex-shrink-0 opacity-70 hover:opacity-100 text-lg leading-none">×</button>
      )}
    </div>
  );
};
