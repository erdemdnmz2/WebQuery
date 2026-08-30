import React from 'react';
import { cn } from '../../lib/cn';

/** Renders a keyboard shortcut hint next to the action it triggers. */
export const Kbd: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => (
  <kbd
    className={cn(
      'inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-xs border border-control-line bg-canvas px-1',
      'font-mono text-[10px] font-medium text-subtle',
      className,
    )}
  >
    {children}
  </kbd>
);
