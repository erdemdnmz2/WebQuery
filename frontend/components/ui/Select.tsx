import React from 'react';
import { Select as RadixSelect } from 'radix-ui';
import { CaretDownIcon, CheckIcon } from '@phosphor-icons/react';
import { cn } from '../../lib/cn';
import { useOptionalField } from './Field';

export interface SelectOption {
  value: string;
  label: string;
  hint?: string;
  disabled?: boolean;
}

export interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  /** Set when the select is used outside a <Field>. */
  ariaLabel?: string;
}

/**
 * Radix-backed select for short, fixed option sets. Longer or searchable
 * lists use <Picker> instead, which adds filtering and keyboard navigation
 * over an arbitrary number of entries.
 */
export const Select: React.FC<SelectProps> = ({
  value,
  onValueChange,
  options,
  placeholder = 'Seçin',
  disabled,
  className,
  ariaLabel,
}) => {
  const field = useOptionalField();

  return (
    <RadixSelect.Root value={value} onValueChange={onValueChange} disabled={disabled}>
      <RadixSelect.Trigger
        id={field?.inputId}
        aria-label={ariaLabel}
        className={cn(
          'group inline-flex h-8 w-full items-center justify-between gap-2 rounded-sm border border-control-line bg-surface px-2.5',
          'text-[13px] text-fg transition-[border-color,background-color] duration-[var(--dur-fast)] ease-standard',
          'hover:border-line-strong data-[state=open]:border-accent',
          'disabled:cursor-not-allowed disabled:bg-sunken disabled:text-subtle',
          className,
        )}
      >
        <RadixSelect.Value placeholder={<span className="text-subtle">{placeholder}</span>} />
        <RadixSelect.Icon asChild>
          <CaretDownIcon
            size={13}
            weight="bold"
            className="shrink-0 text-subtle transition-transform duration-[var(--dur-fast)] group-data-[state=open]:rotate-180"
          />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>

      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          sideOffset={4}
          className={cn(
            'z-[var(--z-overlay)] max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden',
            'rounded-md border border-line bg-raised shadow-overlay',
            'data-[state=open]:animate-[menu-in_var(--dur)_var(--ease)]',
          )}
        >
          <RadixSelect.Viewport className="p-1">
            {options.map((option) => (
              <RadixSelect.Item
                key={option.value}
                value={option.value}
                disabled={option.disabled}
                className={cn(
                  'relative flex cursor-default select-none items-center gap-2 rounded-xs py-1.5 pl-7 pr-2.5',
                  'text-[13px] text-fg outline-none',
                  'data-[highlighted]:bg-hover data-[state=checked]:text-accent',
                  'data-[disabled]:pointer-events-none data-[disabled]:opacity-45',
                )}
              >
                <RadixSelect.ItemIndicator className="absolute left-2 flex">
                  <CheckIcon size={13} weight="bold" />
                </RadixSelect.ItemIndicator>
                <RadixSelect.ItemText>{option.label}</RadixSelect.ItemText>
                {option.hint && <span className="ml-auto font-mono text-[11px] text-subtle">{option.hint}</span>}
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
};
