import React, { useMemo, useRef, useState } from 'react';
import { Popover } from 'radix-ui';
import { CaretUpDownIcon, CheckIcon, MagnifyingGlassIcon } from '@phosphor-icons/react';
import { cn } from '../../lib/cn';

export interface PickerItem {
  value: string;
  label: string;
  /** Secondary line, e.g. a workspace description or a server technology. */
  meta?: string;
  trailing?: React.ReactNode;
  disabled?: boolean;
}

export interface PickerProps {
  value: string | null;
  onChange: (value: string) => void;
  items: PickerItem[];
  placeholder: string;
  /** Accessible name for the trigger. */
  label: string;
  disabled?: boolean;
  emptyMessage?: string;
  searchPlaceholder?: string;
  /** Rendered above the list, e.g. a "create new" affordance. */
  header?: (close: () => void) => React.ReactNode;
  triggerClassName?: string;
  leading?: React.ReactNode;
  /** Filtering appears once the list is long enough to need it. */
  searchThreshold?: number;
}

/**
 * Filterable single-select over an arbitrarily long list. Arrow keys move the
 * active option, Enter commits it and Escape closes without changing the
 * value, so the whole control is reachable without a mouse.
 */
export const Picker: React.FC<PickerProps> = ({
  value,
  onChange,
  items,
  placeholder,
  label,
  disabled,
  emptyMessage = 'Kayıt bulunamadı',
  searchPlaceholder = 'Ara',
  header,
  triggerClassName,
  leading,
  searchThreshold = 7,
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('tr');
    if (!needle) return items;
    return items.filter(
      (item) =>
        item.label.toLocaleLowerCase('tr').includes(needle) ||
        (item.meta ?? '').toLocaleLowerCase('tr').includes(needle),
    );
  }, [items, query]);

  const selected = items.find((item) => item.value === value) ?? null;
  const showSearch = items.length >= searchThreshold;

  const close = () => {
    setOpen(false);
    setQuery('');
    setActiveIndex(0);
  };

  const commit = (item: PickerItem) => {
    if (item.disabled) return;
    onChange(item.value);
    close();
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((current) => {
        const next = event.key === 'ArrowDown' ? current + 1 : current - 1;
        const clamped = (next + filtered.length) % Math.max(filtered.length, 1);
        listRef.current
          ?.querySelectorAll('[data-picker-option]')
          [clamped]?.scrollIntoView({ block: 'nearest' });
        return clamped;
      });
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      const item = filtered[activeIndex];
      if (item) commit(item);
    }
  };

  return (
    <Popover.Root
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setQuery('');
          setActiveIndex(0);
        }
      }}
    >
      <Popover.Trigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-label={label}
          className={cn(
            'group flex h-8 items-center justify-between gap-2 rounded-sm border border-control-line bg-surface px-2.5',
            'text-[13px] text-fg transition-[border-color,background-color] duration-[var(--dur-fast)] ease-standard',
            'hover:border-line-strong data-[state=open]:border-accent',
            'disabled:cursor-not-allowed disabled:bg-sunken disabled:text-subtle',
            triggerClassName,
          )}
        >
          <span className="flex min-w-0 items-center gap-2">
            {leading}
            <span className={cn('truncate', !selected && 'text-subtle')}>{selected?.label ?? placeholder}</span>
          </span>
          <CaretUpDownIcon size={13} className="shrink-0 text-subtle" />
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={4}
          collisionPadding={12}
          onKeyDown={onKeyDown}
          className={cn(
            'z-[var(--z-overlay)] flex max-h-80 w-[min(340px,calc(100vw-2rem))] flex-col overflow-hidden',
            'rounded-md border border-line bg-raised shadow-overlay',
            'data-[state=open]:animate-[menu-in_var(--dur)_var(--ease)]',
          )}
        >
          {showSearch && (
            <div className="flex items-center gap-2 border-b border-line px-2.5">
              <MagnifyingGlassIcon size={13} className="shrink-0 text-subtle" />
              <input
                autoFocus
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setActiveIndex(0);
                }}
                placeholder={searchPlaceholder}
                aria-label={searchPlaceholder}
                className="h-8 w-full bg-transparent text-[13px] outline-none"
              />
            </div>
          )}

          {header?.(close)}

          <div ref={listRef} role="listbox" aria-label={label} className="min-h-0 flex-1 overflow-y-auto p-1">
            {filtered.length === 0 ? (
              <p className="px-2 py-6 text-center text-[12.5px] text-subtle">{emptyMessage}</p>
            ) : (
              filtered.map((item, index) => {
                const isSelected = item.value === value;
                return (
                  <button
                    key={item.value}
                    type="button"
                    data-picker-option
                    role="option"
                    aria-selected={isSelected}
                    disabled={item.disabled}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => commit(item)}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-xs px-2 py-1.5 text-left outline-none',
                      'disabled:pointer-events-none disabled:opacity-45',
                      index === activeIndex && 'bg-hover',
                    )}
                  >
                    <span className="flex w-3.5 shrink-0 justify-center">
                      {isSelected && <CheckIcon size={12} weight="bold" className="text-accent" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={cn('block truncate text-[13px]', isSelected ? 'text-accent' : 'text-fg')}>
                        {item.label}
                      </span>
                      {item.meta && <span className="block truncate text-[11.5px] text-subtle">{item.meta}</span>}
                    </span>
                    {item.trailing}
                  </button>
                );
              })
            )}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
};
