import React from 'react';
import { cn } from '../../lib/cn';

/**
 * A single geometric mark: a bounded result set with one row selected. It is
 * the only place the accent hue appears purely for identity.
 */
export const BrandMark: React.FC<{ className?: string; size?: number }> = ({ className, size = 20 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 20 20"
    fill="none"
    aria-hidden
    className={cn('shrink-0', className)}
  >
    <rect x="0.75" y="0.75" width="18.5" height="18.5" rx="4.25" stroke="currentColor" strokeWidth="1.5" />
    <path d="M4.5 7.25h11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.45" />
    <path d="M4.5 10.5h11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <path d="M4.5 13.75h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.45" />
  </svg>
);
