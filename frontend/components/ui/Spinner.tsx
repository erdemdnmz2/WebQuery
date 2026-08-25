import React from 'react';
import { cn } from '../../lib/cn';

/**
 * Indeterminate progress for actions whose duration cannot be predicted.
 * Skeletons cover everything whose final shape is known, so this is reserved
 * for buttons and remote execution.
 */
export const Spinner: React.FC<{ className?: string; label?: string }> = ({ className, label }) => (
  <span
    role="status"
    aria-label={label ?? 'Yükleniyor'}
    className={cn(
      'inline-block size-3.5 shrink-0 rounded-full border-[1.5px] border-current border-r-transparent align-[-2px] animate-spin-slow',
      className,
    )}
  />
);
