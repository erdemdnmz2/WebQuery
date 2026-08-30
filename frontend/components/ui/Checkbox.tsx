import React from 'react';
import { Checkbox as RadixCheckbox } from 'radix-ui';
import { CheckIcon, MinusIcon } from '@phosphor-icons/react';
import { cn } from '../../lib/cn';

export interface CheckboxProps {
  checked: boolean | 'indeterminate';
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  id?: string;
  ariaLabel?: string;
}

export const Checkbox: React.FC<CheckboxProps> = ({
  checked,
  onCheckedChange,
  disabled,
  className,
  id,
  ariaLabel,
}) => (
  <RadixCheckbox.Root
    id={id}
    checked={checked}
    disabled={disabled}
    aria-label={ariaLabel}
    onCheckedChange={(next) => onCheckedChange(next === true)}
    className={cn(
      'flex size-[15px] shrink-0 items-center justify-center rounded-xs border border-control-line bg-surface',
      'transition-[background-color,border-color] duration-[var(--dur-fast)] ease-standard',
      'hover:border-accent',
      'data-[state=checked]:border-accent data-[state=checked]:bg-accent data-[state=checked]:text-accent-fg',
      'data-[state=indeterminate]:border-accent data-[state=indeterminate]:bg-accent data-[state=indeterminate]:text-accent-fg',
      'disabled:cursor-not-allowed disabled:opacity-45',
      className,
    )}
  >
    <RadixCheckbox.Indicator className="flex">
      {checked === 'indeterminate' ? <MinusIcon size={10} weight="bold" /> : <CheckIcon size={10} weight="bold" />}
    </RadixCheckbox.Indicator>
  </RadixCheckbox.Root>
);
