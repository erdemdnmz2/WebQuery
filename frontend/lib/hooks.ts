import { useEffect, useRef, useState } from 'react';

type HotkeyHandler = (event: KeyboardEvent) => void;

interface HotkeyOptions {
  /** Fire even while the user is typing in an input or the SQL editor. */
  allowInEditable?: boolean;
  enabled?: boolean;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
}

/**
 * Binds a single keyboard shortcut. `combo` is written as `mod+k`, `shift+/`
 * or a bare key such as `escape`; `mod` maps to Command on macOS and Control
 * everywhere else.
 */
export function useHotkey(combo: string, handler: HotkeyHandler, options: HotkeyOptions = {}): void {
  const { allowInEditable = false, enabled = true } = options;
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    if (!enabled) return;

    const parts = combo.toLowerCase().split('+');
    const key = parts[parts.length - 1];
    const needsMod = parts.includes('mod');
    const needsShift = parts.includes('shift');
    const needsAlt = parts.includes('alt');

    const onKeyDown = (event: KeyboardEvent) => {
      if (!allowInEditable && isEditableTarget(event.target)) return;
      const mod = event.metaKey || event.ctrlKey;
      if (needsMod !== mod) return;
      if (needsShift !== event.shiftKey) return;
      if (needsAlt !== event.altKey) return;
      if (event.key.toLowerCase() !== key) return;
      handlerRef.current(event);
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [combo, allowInEditable, enabled]);
}

/** True on macOS, so shortcut hints show the right glyph. */
export function useIsMac(): boolean {
  const [isMac] = useState(() =>
    typeof navigator !== 'undefined' && /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent),
  );
  return isMac;
}

/** Persists a value to localStorage without letting storage failures crash the app. */
export function usePersistentState<T>(key: string, initial: T): [T, (next: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch {
      return initial;
    }
  });

  const update = (next: T) => {
    setValue(next);
    try {
      window.localStorage.setItem(key, JSON.stringify(next));
    } catch {
      /* Non-fatal. */
    }
  };

  return [value, update];
}
