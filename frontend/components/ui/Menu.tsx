import React from 'react';
import { DropdownMenu } from 'radix-ui';
import { CheckIcon } from '@phosphor-icons/react';
import { cn } from '../../lib/cn';

export const Menu = DropdownMenu.Root;
export const MenuTrigger = DropdownMenu.Trigger;

export const MenuContent: React.FC<{
  children: React.ReactNode;
  align?: 'start' | 'center' | 'end';
  className?: string;
  sideOffset?: number;
}> = ({ children, align = 'end', className, sideOffset = 6 }) => (
  <DropdownMenu.Portal>
    <DropdownMenu.Content
      align={align}
      sideOffset={sideOffset}
      collisionPadding={12}
      className={cn(
        'z-[var(--z-overlay)] min-w-52 overflow-hidden rounded-md border border-line bg-raised p-1 shadow-overlay',
        'data-[state=open]:animate-[menu-in_var(--dur)_var(--ease)]',
        className,
      )}
    >
      {children}
    </DropdownMenu.Content>
  </DropdownMenu.Portal>
);

const itemClasses = cn(
  'flex cursor-default select-none items-center gap-2.5 rounded-xs px-2 py-1.5 text-[13px] text-fg outline-none',
  'data-[highlighted]:bg-hover',
  'data-[disabled]:pointer-events-none data-[disabled]:opacity-45',
);

export const MenuItem: React.FC<{
  children: React.ReactNode;
  onSelect?: () => void;
  icon?: React.ReactNode;
  shortcut?: React.ReactNode;
  disabled?: boolean;
  destructive?: boolean;
}> = ({ children, onSelect, icon, shortcut, disabled, destructive }) => (
  <DropdownMenu.Item
    disabled={disabled}
    onSelect={onSelect}
    className={cn(itemClasses, destructive && 'text-danger data-[highlighted]:bg-danger-soft')}
  >
    {icon && <span className="flex w-4 shrink-0 justify-center text-subtle">{icon}</span>}
    <span className="flex-1 truncate">{children}</span>
    {shortcut && <span className="shrink-0">{shortcut}</span>}
  </DropdownMenu.Item>
);

export const MenuRadioGroup: React.FC<{
  value: string;
  onValueChange: (value: string) => void;
  children: React.ReactNode;
}> = ({ value, onValueChange, children }) => (
  <DropdownMenu.RadioGroup value={value} onValueChange={onValueChange}>
    {children}
  </DropdownMenu.RadioGroup>
);

export const MenuRadioItem: React.FC<{
  value: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
}> = ({ value, children, icon }) => (
  <DropdownMenu.RadioItem value={value} className={itemClasses}>
    <span className="flex w-4 shrink-0 justify-center text-subtle">
      <DropdownMenu.ItemIndicator>
        <CheckIcon size={13} weight="bold" className="text-accent" />
      </DropdownMenu.ItemIndicator>
      {icon && <span className="group-data-[state=checked]:hidden">{icon}</span>}
    </span>
    <span className="flex-1 truncate">{children}</span>
  </DropdownMenu.RadioItem>
);

export const MenuLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <DropdownMenu.Label className="px-2 py-1.5 text-[11px] font-medium tracking-wide text-subtle">
    {children}
  </DropdownMenu.Label>
);

export const MenuSeparator: React.FC = () => (
  <DropdownMenu.Separator className="-mx-1 my-1 h-px bg-line" />
);
