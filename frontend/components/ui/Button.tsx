import React from 'react';
import { cn } from '../../lib/cn';
import { Spinner } from './Spinner';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'quiet';
type Size = 'sm' | 'md' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  /** Rendered before the label. Omitted automatically while loading. */
  icon?: React.ReactNode;
  iconAfter?: React.ReactNode;
  fullWidth?: boolean;
}

/*
 * Primary is ink rather than a brand hue. In a console where colour marks
 * query risk, the confirm button must not read as another status chip.
 */
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-primary-fg hover:bg-primary-hover',
  secondary: 'bg-surface text-fg border border-control-line hover:bg-hover hover:border-fg-subtle',
  ghost: 'bg-transparent text-muted hover:bg-hover hover:text-fg',
  danger: 'bg-transparent text-danger border border-danger-line hover:bg-danger-soft',
  quiet: 'bg-transparent text-muted underline-offset-4 hover:text-fg hover:underline',
};

const SIZES: Record<Size, string> = {
  sm: 'h-7 gap-1.5 px-2.5 text-[13px]',
  md: 'h-8 gap-2 px-3 text-[13px]',
  lg: 'h-9 gap-2 px-4 text-sm',
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'secondary',
    size = 'md',
    loading = false,
    icon,
    iconAfter,
    fullWidth,
    className,
    children,
    disabled,
    type = 'button',
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading;

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex select-none items-center justify-center whitespace-nowrap rounded-sm font-medium',
        'transition-[background-color,border-color,color,transform] duration-[var(--dur-fast)] ease-standard',
        'active:translate-y-px',
        'disabled:pointer-events-none disabled:opacity-45',
        VARIANTS[variant],
        SIZES[size],
        fullWidth && 'w-full',
        variant === 'quiet' && 'h-auto px-0',
        className,
      )}
      {...rest}
    >
      {loading ? <Spinner /> : icon}
      {children}
      {!loading && iconAfter}
    </button>
  );
});

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /** Required: an icon-only control needs an accessible name. */
  label: string;
}

const ICON_SIZES: Record<Size, string> = {
  sm: 'size-7',
  md: 'size-8',
  lg: 'size-9',
};

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { variant = 'ghost', size = 'md', label, className, children, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-sm',
        'transition-[background-color,border-color,color,transform] duration-[var(--dur-fast)] ease-standard',
        'active:translate-y-px disabled:pointer-events-none disabled:opacity-45',
        VARIANTS[variant],
        ICON_SIZES[size],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
});
