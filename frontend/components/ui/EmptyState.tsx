import React from 'react';
import { cn } from '../../lib/cn';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  /** One sentence that says what to do next, not what went missing. */
  description?: string;
  action?: React.ReactNode;
  className?: string;
  size?: 'sm' | 'md';
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className,
  size = 'md',
}) => (
  <div
    className={cn(
      'flex flex-col items-center justify-center text-center',
      size === 'md' ? 'gap-3 px-6 py-16' : 'gap-2 px-4 py-10',
      className,
    )}
  >
    {icon && (
      <span className="mb-1 flex size-9 items-center justify-center rounded-md border border-line bg-sunken text-subtle">
        {icon}
      </span>
    )}
    <h3 className={cn('font-medium text-fg', size === 'md' ? 'text-sm' : 'text-[13px]')}>{title}</h3>
    {description && <p className="max-w-[46ch] text-[13px] leading-relaxed text-subtle">{description}</p>}
    {action && <div className="mt-2">{action}</div>}
  </div>
);
