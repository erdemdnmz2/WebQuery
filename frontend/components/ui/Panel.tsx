import React from 'react';
import { cn } from '../../lib/cn';

export interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Removes the outer padding so tables and editors can bleed to the edge. */
  flush?: boolean;
  as?: 'div' | 'section' | 'article' | 'aside';
}

/**
 * The single container surface in the product. Hierarchy comes from the
 * surface ladder and a hairline border; drop shadows are reserved for true
 * overlays so nothing on the page floats without reason.
 */
export const Panel: React.FC<PanelProps> = ({ flush, className, as: Tag = 'div', children, ...rest }) => (
  <Tag
    className={cn(
      'min-w-0 rounded-md border border-line bg-surface',
      !flush && 'p-4',
      className,
    )}
    {...rest}
  >
    {children}
  </Tag>
);

export interface PanelHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  /** Compact header for tool panels that sit next to an editor. */
  dense?: boolean;
}

export const PanelHeader: React.FC<PanelHeaderProps> = ({
  title,
  description,
  actions,
  className,
  dense,
}) => (
  <div
    className={cn(
      'flex flex-wrap items-center justify-between gap-3 border-b border-line',
      dense ? 'px-3 py-2' : 'px-4 py-3',
      className,
    )}
  >
    <div className="min-w-0">
      <h2 className={cn('truncate text-fg', dense ? 'text-[12.5px] font-medium' : 'text-[13.5px] font-medium')}>
        {title}
      </h2>
      {description && <p className="mt-0.5 truncate text-[12px] text-subtle">{description}</p>}
    </div>
    {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
  </div>
);
