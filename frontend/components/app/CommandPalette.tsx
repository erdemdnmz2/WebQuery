import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Dialog as RadixDialog } from 'radix-ui';
import { useNavigate } from 'react-router-dom';
import {
  DatabaseIcon,
  GearSixIcon,
  MagnifyingGlassIcon,
  MoonIcon,
  PlusIcon,
  SignOutIcon,
  SquaresFourIcon,
  SunIcon,
  TerminalWindowIcon,
} from '@phosphor-icons/react';
import { cn } from '../../lib/cn';
import { useTheme } from '../../lib/theme';
import { useSession } from '../../lib/session';
import { statusMeta } from '../../lib/workspace-status';
import { Kbd } from '../ui/Kbd';
import type { Workspace } from '../../types';

interface Command {
  id: string;
  label: string;
  group: string;
  icon: React.ReactNode;
  keywords?: string;
  hint?: string;
  run: () => void;
}

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspaces: Workspace[];
}

/**
 * One keyboard entry point to everything: navigation, the theme, sign out and
 * every saved workspace. It exists because this product is used all day by
 * people who would rather not reach for a mouse to switch context.
 */
export const CommandPalette: React.FC<CommandPaletteProps> = ({ open, onOpenChange, workspaces }) => {
  const navigate = useNavigate();
  const { user, signOut } = useSession();
  const { preference, setPreference } = useTheme();
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      setQuery('');
      setActiveIndex(0);
    }
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const close = () => onOpenChange(false);
    const go = (path: string) => () => {
      close();
      navigate(path);
    };

    const base: Command[] = [
      {
        id: 'nav-workspaces',
        label: "Workspaces",
        group: "Navigate",
        icon: <SquaresFourIcon size={15} />,
        keywords: "workspace list home",
        run: go('/'),
      },
      {
        id: 'nav-studio',
        label: 'SQL Studio',
        group: "Navigate",
        icon: <TerminalWindowIcon size={15} />,
        keywords: "sql editor query",
        run: go('/editor'),
      },
      {
        id: 'new-workspace',
        label: "Write a new query",
        group: "Action",
        icon: <PlusIcon size={15} />,
        keywords: "create new query",
        run: go('/editor'),
      },
    ];

    if (user?.is_admin) {
      base.push({
        id: 'nav-admin',
        label: "Administration panel",
        group: "Navigate",
        icon: <GearSixIcon size={15} />,
        keywords: "admin approval masking database",
        run: go('/admin'),
      });
    }

    for (const workspace of workspaces) {
      const meta = statusMeta(workspace.status);
      base.push({
        id: `ws-${workspace.id}`,
        label: workspace.name,
        group: "Workspaces",
        icon: <DatabaseIcon size={15} />,
        keywords: `${workspace.servername} ${workspace.database_name} ${workspace.description ?? ''}`,
        hint: meta.label,
        run: go(`/editor/${workspace.id}`),
      });
    }

    base.push(
      {
        id: 'theme-light',
        label: "Switch to light theme",
        group: "Appearance",
        icon: <SunIcon size={15} />,
        keywords: "theme light",
        hint: preference === 'light' ? "Active" : undefined,
        run: () => {
          setPreference('light');
          close();
        },
      },
      {
        id: 'theme-dark',
        label: "Switch to dark theme",
        group: "Appearance",
        icon: <MoonIcon size={15} />,
        keywords: "theme dark",
        hint: preference === 'dark' ? "Active" : undefined,
        run: () => {
          setPreference('dark');
          close();
        },
      },
      {
        id: 'sign-out',
        label: "Sign out",
        group: "Account",
        icon: <SignOutIcon size={15} />,
        keywords: "sign out logout",
        run: () => {
          close();
          void signOut().then(() => navigate('/login'));
        },
      },
    );

    return base;
  }, [navigate, onOpenChange, preference, setPreference, signOut, user?.is_admin, workspaces]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("en");
    if (!needle) return commands;
    return commands.filter((command) =>
      `${command.label} ${command.group} ${command.keywords ?? ''}`.toLocaleLowerCase("en").includes(needle),
    );
  }, [commands, query]);

  const grouped = useMemo(() => {
    const map = new Map<string, Command[]>();
    for (const command of filtered) {
      const list = map.get(command.group) ?? [];
      list.push(command);
      map.set(command.group, list);
    }
    return [...map.entries()];
  }, [filtered]);

  const flat = useMemo(() => grouped.flatMap(([, items]) => items), [grouped]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((current) => {
        const next = event.key === 'ArrowDown' ? current + 1 : current - 1;
        const clamped = (next + flat.length) % Math.max(flat.length, 1);
        listRef.current?.querySelectorAll('[data-command]')[clamped]?.scrollIntoView({ block: 'nearest' });
        return clamped;
      });
    } else if (event.key === 'Enter') {
      event.preventDefault();
      flat[activeIndex]?.run();
    }
  };

  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay
          className={cn(
            'fixed inset-0 z-[var(--z-overlay)] bg-[oklch(0.15_0.01_85_/_0.45)]',
            'data-[state=open]:animate-[overlay-in_var(--dur)_var(--ease)]',
          )}
        />
        <RadixDialog.Content
          onKeyDown={onKeyDown}
          className={cn(
            'fixed left-1/2 top-[12vh] z-[var(--z-dialog)] flex max-h-[70dvh] w-[min(560px,calc(100vw-2rem))] -translate-x-1/2 flex-col',
            'overflow-hidden rounded-lg border border-line bg-raised shadow-overlay',
            'data-[state=open]:animate-[dialog-in_var(--dur-slow)_var(--ease)]',
          )}
        >
          <RadixDialog.Title className="sr-only">Command palette</RadixDialog.Title>
          <RadixDialog.Description className="sr-only">
            Search pages, workspaces and actions.
          </RadixDialog.Description>

          <div className="flex items-center gap-2.5 border-b border-line px-3.5">
            <MagnifyingGlassIcon size={15} className="shrink-0 text-subtle" />
            <input
              autoFocus
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActiveIndex(0);
              }}
              placeholder="Search pages, workspaces or actions"
              aria-label="Search commands"
              className="h-11 w-full bg-transparent text-[14px] outline-none"
            />
            <Kbd>esc</Kbd>
          </div>

          <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto p-1.5">
            {flat.length === 0 ? (
              <p className="px-3 py-10 text-center text-[13px] text-subtle">
                &ldquo;{query}&rdquo; — no results found.
              </p>
            ) : (
              grouped.map(([group, items]) => (
                <div key={group} className="mb-1">
                  <p className="px-2 py-1.5 text-[11px] font-medium text-subtle">{group}</p>
                  {items.map((command) => {
                    const index = flat.indexOf(command);
                    return (
                      <button
                        key={command.id}
                        type="button"
                        data-command
                        onMouseEnter={() => setActiveIndex(index)}
                        onClick={command.run}
                        className={cn(
                          'flex w-full items-center gap-2.5 rounded-xs px-2 py-2 text-left outline-none',
                          index === activeIndex && 'bg-hover',
                        )}
                      >
                        <span className="flex w-4 shrink-0 justify-center text-subtle">{command.icon}</span>
                        <span className="min-w-0 flex-1 truncate text-[13px] text-fg">{command.label}</span>
                        {command.hint && (
                          <span className="shrink-0 text-[11.5px] text-subtle">{command.hint}</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              ))
            )}
          </div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
};
