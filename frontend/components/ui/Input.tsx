import React from 'react';
import { cn } from '../../lib/cn';
import { controlClasses, useField } from './Field';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Rendered inside the control on the leading edge. */
  icon?: React.ReactNode;
  /** Rendered inside the control on the trailing edge. */
  addon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, icon, addon, ...rest },
  ref,
) {
  const { inputId, hintId, errorId, invalid } = useField();

  const control = (
    <input
      ref={ref}
      id={inputId}
      aria-invalid={invalid || undefined}
      aria-describedby={cn(rest['aria-describedby'], invalid ? errorId : hintId) || undefined}
      className={cn(
        controlClasses,
        'h-8 focus:ring-2 focus:ring-accent/25',
        icon && 'pl-8',
        addon && 'pr-9',
        className,
      )}
      {...rest}
    />
  );

  if (!icon && !addon) return control;

  return (
    <div className="relative flex items-center">
      {icon && (
        <span aria-hidden className="pointer-events-none absolute left-2.5 flex text-subtle">
          {icon}
        </span>
      )}
      {control}
      {addon && <span className="absolute right-1.5 flex items-center">{addon}</span>}
    </div>
  );
});

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, rows = 3, ...rest }, ref) {
    const { inputId, hintId, errorId, invalid } = useField();
    return (
      <textarea
        ref={ref}
        id={inputId}
        rows={rows}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? errorId : hintId}
        className={cn(controlClasses, 'resize-y py-2 leading-relaxed focus:ring-2 focus:ring-accent/25', className)}
        {...rest}
      />
    );
  },
);

/** Read-only value display that still looks like part of the form. */
export const ReadonlyValue: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className,
}) => (
  <div
    className={cn(
      'flex h-8 items-center rounded-sm border border-line bg-sunken px-2.5 font-mono text-[12.5px] text-muted',
      className,
    )}
  >
    {children}
  </div>
);
