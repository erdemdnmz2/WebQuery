import React from 'react';
import { Tooltip as RadixTooltip } from 'radix-ui';
import { cn } from '../../lib/cn';

export const TooltipProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <RadixTooltip.Provider delayDuration={400} skipDelayDuration={200}>
    {children}
  </RadixTooltip.Provider>
);

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: 'top' | 'right' | 'bottom' | 'left';
  /** Tooltips never carry information that exists nowhere else. */
  disabled?: boolean;
}

export const Tooltip: React.FC<TooltipProps> = ({ content, children, side = 'top', disabled }) => {
  if (disabled) return <>{children}</>;
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          side={side}
          sideOffset={6}
          collisionPadding={8}
          className={cn(
            'z-[var(--z-tooltip)] max-w-64 rounded-sm border border-line bg-raised px-2 py-1',
            'text-[12px] leading-snug text-fg shadow-overlay',
            'data-[state=delayed-open]:animate-[menu-in_var(--dur-fast)_var(--ease)]',
          )}
        >
          {content}
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
};
