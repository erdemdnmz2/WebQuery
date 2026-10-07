import React, { createContext, useContext, useId } from 'react';
import { cn } from '../../lib/cn';

interface FieldContextValue {
  inputId: string;
  hintId: string;
  errorId: string;
  invalid: boolean;
}

const FieldContext = createContext<FieldContextValue | null>(null);

export function useField() {
  const ctx = useContext(FieldContext);
  if (!ctx) {
    throw new Error('Input and Textarea must be wrapped in <Field>');
  }
  return ctx;
}

/** For controls that are valid both inside and outside a <Field>. */
export function useOptionalField(): FieldContextValue | null {
  return useContext(FieldContext);
}

export interface FieldProps {
  label: string;
  /** Persistent guidance. Never used as a substitute for the label. */
  hint?: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
  /** Rendered on the label row, right aligned. Useful for character counts. */
  aside?: React.ReactNode;
}

/**
 * Label above the control, hint under the label, error under the control.
 * The label is always rendered, so no control in this product uses its
 * placeholder as a label.
 */
export const Field: React.FC<FieldProps> = ({
  label,
  hint,
  error,
  required,
  className,
  children,
  aside,
}) => {
  const base = useId();
  const value: FieldContextValue = {
    inputId: `${base}-input`,
    hintId: `${base}-hint`,
    errorId: `${base}-error`,
    invalid: Boolean(error),
  };

  return (
    <FieldContext.Provider value={value}>
      <div className={cn('flex flex-col gap-1.5', className)}>
        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor={value.inputId} className="text-[12.5px] font-medium text-muted">
            {label}
            {required && (
              <span aria-hidden className="ml-1 text-danger">
                *
              </span>
            )}
          </label>
          {aside}
        </div>
        {hint && (
          <p id={value.hintId} className="text-[12px] leading-snug text-subtle">
            {hint}
          </p>
        )}
        {children}
        {error && (
          <p id={value.errorId} className="flex items-start gap-1.5 text-[12px] leading-snug text-danger">
            {error}
          </p>
        )}
      </div>
    </FieldContext.Provider>
  );
};

/** Shared surface treatment for every text-entry control. */
export const controlClasses = cn(
  'w-full rounded-sm border border-control-line bg-surface px-2.5 text-[13px] text-fg',
  'transition-[border-color,background-color] duration-[var(--dur-fast)] ease-standard',
  'hover:border-line-strong',
  'focus:border-accent focus:outline-none focus-visible:outline-none',
  'disabled:cursor-not-allowed disabled:bg-sunken disabled:text-subtle',
  'aria-[invalid=true]:border-danger',
);
