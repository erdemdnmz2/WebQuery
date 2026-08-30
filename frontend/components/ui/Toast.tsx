import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { Toast as RadixToast } from 'radix-ui';
import { CheckCircleIcon, InfoIcon, WarningCircleIcon, WarningIcon, XIcon } from '@phosphor-icons/react';
import { cn } from '../../lib/cn';
import { IconButton } from './Button';

export type ToastTone = 'success' | 'danger' | 'warning' | 'info';

interface ToastRecord {
  id: number;
  tone: ToastTone;
  title: string;
  description?: string;
}

interface ToastApi {
  /** Transient confirmation. Anything the user must act on belongs inline. */
  notify: (toast: Omit<ToastRecord, 'id'>) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  /** An outcome that is neither failure nor completion, such as a pending review. */
  warning: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TONE_ICON: Record<ToastTone, React.ReactNode> = {
  success: <CheckCircleIcon size={16} weight="fill" className="text-success" />,
  danger: <WarningCircleIcon size={16} weight="fill" className="text-danger" />,
  warning: <WarningIcon size={16} weight="fill" className="text-warning" />,
  info: <InfoIcon size={16} weight="fill" className="text-accent" />,
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);

  const notify = useCallback((toast: Omit<ToastRecord, 'id'>) => {
    setToasts((current) => [...current, { ...toast, id: Date.now() + Math.random() }]);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      notify,
      success: (title, description) => notify({ tone: 'success', title, description }),
      error: (title, description) => notify({ tone: 'danger', title, description }),
      warning: (title, description) => notify({ tone: 'warning', title, description }),
    }),
    [notify],
  );

  const dismiss = (id: number) => setToasts((current) => current.filter((toast) => toast.id !== id));

  return (
    <ToastContext.Provider value={api}>
      <RadixToast.Provider swipeDirection="right" duration={5000}>
        {children}
        {toasts.map((toast) => (
          <RadixToast.Root
            key={toast.id}
            onOpenChange={(open) => {
              if (!open) dismiss(toast.id);
            }}
            className={cn(
              'flex items-start gap-2.5 rounded-md border border-line bg-raised px-3.5 py-3 shadow-overlay',
              'data-[state=open]:animate-[dialog-in_var(--dur-slow)_var(--ease)]',
              'data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)]',
              'data-[swipe=cancel]:translate-x-0 data-[swipe=cancel]:transition-transform',
            )}
          >
            <span className="mt-px shrink-0">{TONE_ICON[toast.tone]}</span>
            <div className="min-w-0 flex-1">
              <RadixToast.Title className="text-[13px] font-medium text-fg">{toast.title}</RadixToast.Title>
              {toast.description && (
                <RadixToast.Description className="mt-0.5 text-[12.5px] leading-snug text-subtle">
                  {toast.description}
                </RadixToast.Description>
              )}
            </div>
            <RadixToast.Close asChild>
              <IconButton label="Kapat" size="sm" className="-mr-1.5 -mt-1 size-6">
                <XIcon size={13} />
              </IconButton>
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="fixed bottom-4 right-4 z-[var(--z-toast)] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2 outline-none" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
};

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx;
}
