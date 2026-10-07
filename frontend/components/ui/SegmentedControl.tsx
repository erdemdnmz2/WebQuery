import React from 'react';
import { cn } from '../../lib/cn';

export interface Segment<T extends string> {
  value: T;
  label: string;
  icon?: React.ReactNode;
  /** Count shown after the label, e.g. the number of pending approvals. */
  count?: number;
}

export interface SegmentedControlProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  segments: Segment<T>[];
  label: string;
  className?: string;
}

/**
 * Tab-style switch built on real radio semantics, so arrow keys move between
 * options and screen readers announce the selected one.
 */
export function SegmentedControl<T extends string>({
  value,
  onChange,
  segments,
  label,
  className,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn('inline-flex items-center gap-0.5 rounded-sm border border-line bg-sunken p-0.5', className)}
    >
      {segments.map((segment) => {
        const active = segment.value === value;
        return (
          <button
            key={segment.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(segment.value)}
            className={cn(
              'inline-flex h-7 items-center gap-1.5 rounded-xs px-2.5 text-[12.5px] font-medium',
              'transition-[background-color,color] duration-[var(--dur-fast)] ease-standard',
              active ? 'bg-surface text-fg shadow-[0_0_0_1px_var(--line)]' : 'text-subtle hover:text-fg',
            )}
          >
            {segment.icon}
            {segment.label}
            {typeof segment.count === 'number' && segment.count > 0 && (
              <span
                className={cn(
                  'ml-0.5 rounded-[var(--r-pill)] px-1.5 text-[10.5px] font-medium leading-[16px]',
                  active ? 'bg-accent-soft text-accent' : 'bg-hover text-subtle',
                )}
              >
                {segment.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
