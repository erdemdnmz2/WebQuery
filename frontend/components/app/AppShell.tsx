import React, { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import {
  DesktopIcon,
  GearSixIcon,
  MagnifyingGlassIcon,
  MoonIcon,
  SignOutIcon,
  SquaresFourIcon,
  SunIcon,
  TerminalWindowIcon,
  UserIcon,
} from '@phosphor-icons/react';
import { cn } from '../../lib/cn';
import { useHotkey, useIsMac } from '../../lib/hooks';
import { useSession } from '../../lib/session';
import { useTheme, type ThemePreference } from '../../lib/theme';
import { useWorkspaces } from '../../lib/workspaces';
import { IconButton } from '../ui/Button';
import { Kbd } from '../ui/Kbd';
import { Menu, MenuContent, MenuItem, MenuLabel, MenuRadioGroup, MenuRadioItem, MenuSeparator, MenuTrigger } from '../ui/Menu';
import { BrandMark } from './BrandMark';
import { CommandPalette } from './CommandPalette';

const NAV = [
  { to: '/', label: 'Çalışma alanları', icon: <SquaresFourIcon size={15} />, end: true },
  { to: '/editor', label: 'SQL Studio', icon: <TerminalWindowIcon size={15} />, end: false },
];

const THEME_LABEL: Record<ThemePreference, string> = {
  system: 'Sistem',
  light: 'Açık',
  dark: 'Koyu',
};

export interface AppShellProps {
  children: React.ReactNode;
  /** Screens that own their own scrolling, such as the studio. */
  fullBleed?: boolean;
}

export const AppShell: React.FC<AppShellProps> = ({ children, fullBleed }) => {
  const { user, signOut } = useSession();
  const { workspaces } = useWorkspaces();
  const { preference, setPreference } = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const navigate = useNavigate();
  const isMac = useIsMac();

  useHotkey('mod+k', () => setPaletteOpen((open) => !open), { allowInEditable: true });

  const handleSignOut = async () => {
    await signOut();
    navigate('/login');
  };

  const navLinkClasses = ({ isActive }: { isActive: boolean }) =>
    cn(
      'relative inline-flex h-8 items-center gap-1.5 rounded-sm px-2.5 text-[13px]',
      'transition-colors duration-[var(--dur-fast)] ease-standard',
      isActive ? 'text-fg' : 'text-subtle hover:bg-hover hover:text-fg',
    );

  return (
    /*
     * A full-bleed route (the editor, the run screen) owns the viewport: its
     * panels scroll internally, so the shell is a fixed height. Ordinary
     * routes keep normal page scrolling.
     */
    <div className={cn('flex flex-col bg-canvas', fullBleed ? 'h-dvh overflow-hidden' : 'min-h-dvh')}>
      <a href="#main" className="skip-link">
        İçeriğe geç
      </a>

      <header className="sticky top-0 z-[var(--z-nav)] border-b border-line bg-canvas">
        <nav
          aria-label="Ana gezinme"
          className="mx-auto flex h-[var(--nav-h)] w-full max-w-[var(--shell-max)] items-center gap-2 px-4 sm:px-6"
        >
          <Link
            to="/"
            className="mr-2 inline-flex items-center gap-2 rounded-sm text-fg transition-opacity hover:opacity-80"
          >
            <BrandMark className="text-accent" />
            <span className="text-[14px] font-medium tracking-tight">WebQuery</span>
          </Link>

          <div className="hidden items-center gap-0.5 md:flex">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClasses}>
                {({ isActive }) => (
                  <>
                    {item.icon}
                    {item.label}
                    {isActive && (
                      <span
                        aria-hidden
                        className="absolute inset-x-2.5 -bottom-[13px] h-0.5 rounded-full bg-accent"
                      />
                    )}
                  </>
                )}
              </NavLink>
            ))}
            {(user?.is_admin || user?.is_platform_owner) && (
              <NavLink to="/admin" className={navLinkClasses}>
                {({ isActive }) => (
                  <>
                    <GearSixIcon size={15} />
                    Yönetim
                    {isActive && (
                      <span
                        aria-hidden
                        className="absolute inset-x-2.5 -bottom-[13px] h-0.5 rounded-full bg-accent"
                      />
                    )}
                  </>
                )}
              </NavLink>
            )}
          </div>

          <div className="ml-auto flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className={cn(
                'hidden h-8 items-center gap-2 rounded-sm border border-line bg-surface pl-2.5 pr-1.5 sm:flex',
                'text-[13px] text-subtle transition-colors duration-[var(--dur-fast)] hover:border-line-strong hover:text-fg',
              )}
            >
              <MagnifyingGlassIcon size={14} />
              <span className="pr-6">Ara</span>
              <Kbd>{isMac ? '⌘' : 'Ctrl'} K</Kbd>
            </button>

            <IconButton
              label="Ara"
              className="sm:hidden"
              onClick={() => setPaletteOpen(true)}
            >
              <MagnifyingGlassIcon size={16} />
            </IconButton>

            <Menu>
              <MenuTrigger asChild>
                <IconButton label="Görünüm ayarları">
                  {preference === 'dark' ? (
                    <MoonIcon size={16} />
                  ) : preference === 'light' ? (
                    <SunIcon size={16} />
                  ) : (
                    <DesktopIcon size={16} />
                  )}
                </IconButton>
              </MenuTrigger>
              <MenuContent>
                <MenuLabel>Tema</MenuLabel>
                <MenuRadioGroup
                  value={preference}
                  onValueChange={(value) => setPreference(value as ThemePreference)}
                >
                  <MenuRadioItem value="system">{THEME_LABEL.system}</MenuRadioItem>
                  <MenuRadioItem value="light">{THEME_LABEL.light}</MenuRadioItem>
                  <MenuRadioItem value="dark">{THEME_LABEL.dark}</MenuRadioItem>
                </MenuRadioGroup>
              </MenuContent>
            </Menu>

            <Menu>
              <MenuTrigger asChild>
                <button
                  type="button"
                  aria-label="Hesap menüsü"
                  className={cn(
                    'inline-flex h-8 items-center gap-2 rounded-sm px-1.5 text-[13px] text-muted',
                    'transition-colors duration-[var(--dur-fast)] hover:bg-hover hover:text-fg',
                  )}
                >
                  <span className="flex size-6 items-center justify-center rounded-xs bg-accent-soft text-[11px] font-medium text-accent">
                    {(user?.username ?? '?').slice(0, 2).toLocaleUpperCase('tr')}
                  </span>
                  <span className="hidden max-w-32 truncate lg:inline">{user?.username ?? 'Misafir'}</span>
                </button>
              </MenuTrigger>
              <MenuContent>
                <div className="px-2 py-1.5">
                  <p className="truncate text-[13px] font-medium text-fg">{user?.username ?? 'Misafir'}</p>
                  <p className="truncate text-[12px] text-subtle">
                    {user?.is_platform_owner ? 'Platform OWNER' : user?.is_admin ? 'Veritabanı yöneticisi' : 'Kullanıcı'}
                  </p>
                </div>
                <MenuSeparator />
                <div className="md:hidden">
                  <MenuItem icon={<SquaresFourIcon size={15} />} onSelect={() => navigate('/')}>
                    Çalışma alanları
                  </MenuItem>
                  <MenuItem icon={<TerminalWindowIcon size={15} />} onSelect={() => navigate('/editor')}>
                    SQL Studio
                  </MenuItem>
                  {(user?.is_admin || user?.is_platform_owner) && (
                    <MenuItem icon={<GearSixIcon size={15} />} onSelect={() => navigate('/admin')}>
                      Yönetim
                    </MenuItem>
                  )}
                  <MenuSeparator />
                </div>
                <MenuItem icon={<UserIcon size={15} />} onSelect={() => setPaletteOpen(true)}>
                  Komut paleti
                </MenuItem>
                <MenuItem icon={<SignOutIcon size={15} />} onSelect={() => void handleSignOut()}>
                  Oturumu kapat
                </MenuItem>
              </MenuContent>
            </Menu>
          </div>
        </nav>
      </header>

      <main
        id="main"
        tabIndex={-1}
        className={cn(
          'flex min-h-0 flex-1 flex-col outline-none',
          fullBleed
            ? 'mx-auto w-full max-w-[var(--shell-max)] px-4 py-4 sm:px-6'
            : 'mx-auto w-full max-w-[var(--shell-max)] px-4 py-7 sm:px-6',
        )}
      >
        {children}
      </main>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} workspaces={workspaces} />
    </div>
  );
};
