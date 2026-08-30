import React, { useCallback, useEffect, useRef, useState } from 'react';
import { cn } from '../../lib/cn';
import { usePersistentState } from '../../lib/hooks';

export interface SplitPaneProps {
  first: React.ReactNode;
  second: React.ReactNode;
  /** Persists the ratio per screen so the layout survives a reload. */
  storageKey: string;
  defaultRatio?: number;
  minRatio?: number;
  maxRatio?: number;
  firstLabel: string;
  secondLabel: string;
  className?: string;
}

/**
 * Two resizable panes with a real separator. The handle is a focusable
 * element with arrow-key support, so the split is adjustable without a mouse,
 * and the layout collapses to a stack below the tablet breakpoint.
 */
export const SplitPane: React.FC<SplitPaneProps> = ({
  first,
  second,
  storageKey,
  defaultRatio = 0.44,
  minRatio = 0.2,
  maxRatio = 0.8,
  firstLabel,
  secondLabel,
  className,
}) => {
  const [ratio, setRatio] = usePersistentState(storageKey, defaultRatio);
  const [dragging, setDragging] = useState(false);
  const container = useRef<HTMLDivElement>(null);

  const clamp = useCallback(
    (value: number) => Math.min(maxRatio, Math.max(minRatio, value)),
    [minRatio, maxRatio],
  );

  useEffect(() => {
    if (!dragging) return;

    const onMove = (event: PointerEvent) => {
      const box = container.current?.getBoundingClientRect();
      if (!box || box.width === 0) return;
      setRatio(clamp((event.clientX - box.left) / box.width));
    };
    const onUp = () => setDragging(false);

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [dragging, clamp, setRatio]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      setRatio(clamp(ratio - 0.02));
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      setRatio(clamp(ratio + 0.02));
    } else if (event.key === 'Home') {
      event.preventDefault();
      setRatio(defaultRatio);
    }
  };

  return (
    <div
      ref={container}
      className={cn('flex min-h-0 flex-col gap-3 lg:flex-row lg:gap-0', className)}
    >
      <div className="flex min-h-[280px] min-w-0 flex-1 lg:flex-none" style={{ flexBasis: `${ratio * 100}%` }}>
        {first}
      </div>

      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Bölme genişliği"
        aria-valuenow={Math.round(ratio * 100)}
        aria-valuemin={Math.round(minRatio * 100)}
        aria-valuemax={Math.round(maxRatio * 100)}
        tabIndex={0}
        onPointerDown={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onKeyDown={onKeyDown}
        className={cn(
          'group relative hidden w-3 shrink-0 cursor-col-resize items-center justify-center lg:flex',
          'focus-visible:outline-none',
        )}
      >
        <span
          className={cn(
            'h-full w-px bg-line transition-colors duration-[var(--dur-fast)]',
            'group-hover:bg-accent group-focus-visible:bg-accent',
            dragging && 'bg-accent',
          )}
        />
      </div>

      <div className="flex min-h-[280px] min-w-0 flex-1">{second}</div>

      <span className="sr-only">
        {firstLabel} ve {secondLabel} arasındaki bölmeyi ok tuşlarıyla ayarlayabilirsiniz.
      </span>
    </div>
  );
};
