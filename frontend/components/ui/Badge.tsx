import React from 'react';
import { cn } from '../../lib/cn';

export type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger';

const TONES: Record<Tone, string> = {
  neutral: 'bg-sunken text-muted border-line',
  accent: 'bg-accent-soft text-accent border-accent-line',
  success: 'bg-success-soft text-success border-success-line',
  warning: 'bg-warning-soft text-warning border-warning-line',
  danger: 'bg-danger-soft text-danger border-danger-line',
};

export interface BadgeProps {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
  /** Renders a leading dot. Reserved for live state, never decoration. */
  dot?: boolean;
  mono?: boolean;
}

/**
 * A small state marker. Badges are the only pill-shaped element in the system;
 * every other surface uses the documented 6/10/14px radius scale.
 */
export const Badge: React.FC<BadgeProps> = ({ tone = 'neutral', children, className, dot, mono }) => (
  <span
    className={cn(
      'inline-flex h-[20px] shrink-0 items-center gap-1.5 rounded-[var(--r-pill)] border px-2',
      'text-[11px] font-medium leading-none',
      mono && 'font-mono text-[10.5px]',
      TONES[tone],
      className,
    )}
  >
    {dot && <span aria-hidden className="size-1.5 rounded-full bg-current" />}
    {children}
  </span>
);

/** Monospace chip for a server, database or column identifier. */
export const Identifier: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className,
}) => (
  <span
    className={cn(
      'inline-flex max-w-full items-center truncate rounded-xs bg-sunken px-1.5 py-0.5',
      'font-mono text-[11.5px] text-muted',
      className,
    )}
  >
    {children}
  </span>
);
