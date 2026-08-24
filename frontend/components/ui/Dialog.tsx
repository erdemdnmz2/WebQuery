import React from 'react';
import { Dialog as RadixDialog } from 'radix-ui';
import { XIcon } from '@phosphor-icons/react';
import { cn } from '../../lib/cn';
import { Button, IconButton } from './Button';

type DialogSize = 'sm' | 'md' | 'lg' | 'xl';

const SIZES: Record<DialogSize, string> = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-5xl',
};

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Rendered under the title. Radix wires it to aria-describedby. */
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: DialogSize;
  /** Prevents dismissal while a request is in flight. */
  busy?: boolean;
}

/**
 * Radix supplies the focus trap, scroll lock, Escape handling and the
 * labelling relationships. This wrapper only supplies the surface.
 */
export const Dialog: React.FC<DialogProps> = ({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  size = 'md',
  busy,
}) => (
  <RadixDialog.Root open={open} onOpenChange={busy ? undefined : onOpenChange}>
    <RadixDialog.Portal>
      <RadixDialog.Overlay
        className={cn(
          'fixed inset-0 z-[var(--z-overlay)] bg-[oklch(0.15_0.01_85_/_0.45)]',
          'data-[state=open]:animate-[overlay-in_var(--dur)_var(--ease)]',
        )}
      />
      <RadixDialog.Content
        onInteractOutside={(event) => {
          if (busy) event.preventDefault();
        }}
        className={cn(
          'fixed left-1/2 top-1/2 z-[var(--z-dialog)] flex max-h-[min(88dvh,760px)] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col',
          'rounded-lg border border-line bg-raised shadow-overlay',
          'data-[state=open]:animate-[dialog-in_var(--dur-slow)_var(--ease)]',
          SIZES[size],
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-3.5">
          <div className="min-w-0">
            <RadixDialog.Title className="text-[14px] font-medium text-fg">{title}</RadixDialog.Title>
            {description ? (
              <RadixDialog.Description className="mt-1 text-[12.5px] leading-relaxed text-subtle">
                {description}
              </RadixDialog.Description>
            ) : (
              <RadixDialog.Description className="sr-only">{title}</RadixDialog.Description>
            )}
          </div>
          <RadixDialog.Close asChild>
            <IconButton label="Kapat" size="sm" disabled={busy} className="-mr-1.5 -mt-1">
              <XIcon size={15} />
            </IconButton>
          </RadixDialog.Close>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>

        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line bg-surface px-5 py-3">
            {footer}
          </div>
        )}
      </RadixDialog.Content>
    </RadixDialog.Portal>
  </RadixDialog.Root>
);

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  /** Extra context, such as the exact object being deleted. */
  children?: React.ReactNode;
}

/**
 * Replaces window.confirm. The destructive action names what it destroys and
 * the cancel action is the one that receives focus first.
 */
export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel = 'Vazgeç',
  destructive,
  busy,
  onConfirm,
  children,
}) => (
  <Dialog
    open={open}
    onOpenChange={onOpenChange}
    title={title}
    description={description}
    size="sm"
    busy={busy}
    footer={
      <>
        <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={busy}>
          {cancelLabel}
        </Button>
        <Button
          variant={destructive ? 'danger' : 'primary'}
          onClick={onConfirm}
          loading={busy}
          className={destructive ? 'border-danger-line bg-danger-soft hover:bg-danger-soft' : undefined}
        >
          {confirmLabel}
        </Button>
      </>
    }
  >
    {children}
  </Dialog>
);
