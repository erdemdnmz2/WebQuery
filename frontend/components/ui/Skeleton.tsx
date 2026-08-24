import React from 'react';
import { cn } from '../../lib/cn';

/**
 * Loading placeholder shaped like the content it replaces. Used instead of a
 * spinner wherever the final layout is already known, which keeps the page
 * from reflowing when data lands.
 */
export const Skeleton: React.FC<{ className?: string }> = ({ className }) => (
  <div
    aria-hidden
    className={cn(
      'rounded-xs bg-[linear-gradient(90deg,var(--bg-sunken)_25%,var(--bg-hover)_50%,var(--bg-sunken)_75%)]',
      'bg-[length:200%_100%] animate-shimmer',
      className,
    )}
  />
);

/** Row-shaped skeleton for list and table loading states. */
export const SkeletonRows: React.FC<{ rows?: number; className?: string }> = ({ rows = 5, className }) => (
  <div className={cn('flex flex-col', className)}>
    {Array.from({ length: rows }).map((_, index) => (
      <div key={index} className="flex items-center gap-4 border-b border-line px-4 py-3.5">
        <Skeleton className="h-3.5 flex-1" />
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-3.5 w-16" />
      </div>
    ))}
  </div>
);
