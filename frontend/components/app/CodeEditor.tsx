import React, { useEffect, useMemo, useRef } from 'react';
import { EditorState, Compartment, type Extension } from '@codemirror/state';
import {
  EditorView,
  keymap,
  lineNumbers,
  highlightActiveLine,
  highlightActiveLineGutter,
  placeholder as placeholderExt,
  drawSelection,
  rectangularSelection,
} from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import { HighlightStyle, bracketMatching, indentOnInput, syntaxHighlighting } from '@codemirror/language';
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap } from '@codemirror/autocomplete';
import { highlightSelectionMatches, searchKeymap } from '@codemirror/search';
import { MSSQL, MySQL, PostgreSQL, sql, type SQLDialect } from '@codemirror/lang-sql';
import { tags } from '@lezer/highlight';
import { cn } from '../../lib/cn';

/*
 * The editor is themed entirely with the product's custom properties, so a
 * theme switch re-paints it without tearing down the EditorView and losing
 * undo history or cursor position.
 */
const editorTheme = EditorView.theme({
  '&': {
    height: '100%',
    backgroundColor: 'var(--bg-sunken)',
    color: 'var(--fg)',
    fontSize: '13px',
  },
  '&.cm-focused': { outline: 'none' },
  '.cm-scroller': {
    fontFamily: 'var(--font-mono, ui-monospace, monospace)',
    lineHeight: '1.65',
  },
  '.cm-content': { padding: '10px 0', caretColor: 'var(--accent)' },
  '.cm-gutters': {
    backgroundColor: 'var(--bg-sunken)',
    color: 'var(--fg-faint)',
    border: 'none',
    paddingRight: '4px',
  },
  '.cm-lineNumbers .cm-gutterElement': { padding: '0 8px 0 12px', minWidth: '34px' },
  '.cm-activeLine': { backgroundColor: 'var(--bg-hover)' },
  '.cm-activeLineGutter': { backgroundColor: 'var(--bg-hover)', color: 'var(--fg-muted)' },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--accent)', borderLeftWidth: '2px' },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
    backgroundColor: 'var(--accent-soft)',
  },
  '.cm-selectionMatch': { backgroundColor: 'var(--bg-active)' },
  '.cm-matchingBracket, &.cm-focused .cm-matchingBracket': {
    backgroundColor: 'var(--accent-soft)',
    outline: '1px solid var(--accent-line)',
  },
  '.cm-placeholder': { color: 'var(--fg-faint)', fontStyle: 'normal' },
  '.cm-tooltip': {
    backgroundColor: 'var(--bg-raised)',
    border: '1px solid var(--line)',
    borderRadius: 'var(--r-md)',
    boxShadow: 'var(--shadow-overlay)',
    overflow: 'hidden',
  },
  '.cm-tooltip-autocomplete > ul > li': { padding: '4px 10px', fontFamily: 'var(--font-mono)' },
  '.cm-tooltip-autocomplete > ul > li[aria-selected]': {
    backgroundColor: 'var(--bg-hover)',
    color: 'var(--fg)',
  },
  '.cm-panels': { backgroundColor: 'var(--bg-surface)', color: 'var(--fg)' },
  '.cm-panels input, .cm-panels button': {
    backgroundColor: 'var(--bg-canvas)',
    border: '1px solid var(--line)',
    borderRadius: 'var(--r-xs)',
    color: 'var(--fg)',
    padding: '2px 6px',
  },
  '.cm-searchMatch': { backgroundColor: 'var(--warning-soft)' },
  '.cm-searchMatch-selected': { backgroundColor: 'var(--accent-soft)' },
});

const highlightStyle = HighlightStyle.define([
  { tag: tags.keyword, color: 'var(--code-keyword)', fontWeight: '500' },
  { tag: [tags.string, tags.special(tags.string)], color: 'var(--code-string)' },
  { tag: [tags.number, tags.bool, tags.null], color: 'var(--code-number)' },
  { tag: [tags.comment, tags.lineComment, tags.blockComment], color: 'var(--code-comment)', fontStyle: 'italic' },
  { tag: [tags.function(tags.variableName), tags.standard(tags.variableName)], color: 'var(--code-fn)' },
  { tag: [tags.operator, tags.punctuation, tags.separator], color: 'var(--code-operator)' },
  { tag: [tags.typeName, tags.className], color: 'var(--code-fn)' },
  { tag: tags.variableName, color: 'var(--fg)' },
]);

function dialectFor(technology?: string): SQLDialect {
  switch ((technology ?? '').toLowerCase()) {
    case 'postgres':
    case 'postgresql':
      return PostgreSQL;
    case 'mysql':
      return MySQL;
    default:
      return MSSQL;
  }
}

export interface CodeEditorProps {
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  /** Fired on Cmd/Ctrl+Enter so the primary action is reachable from the keys. */
  onRun?: () => void;
  technology?: string;
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  value,
  onChange,
  readOnly = false,
  onRun,
  technology,
  placeholder = 'SELECT ...',
  className,
  ariaLabel = 'SQL düzenleyici',
}) => {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  const onRunRef = useRef(onRun);
  onChangeRef.current = onChange;
  onRunRef.current = onRun;

  const readOnlyCompartment = useMemo(() => new Compartment(), []);
  const languageCompartment = useMemo(() => new Compartment(), []);

  useEffect(() => {
    if (!host.current || view.current) return;

    const extensions: Extension[] = [
      lineNumbers(),
      highlightActiveLine(),
      highlightActiveLineGutter(),
      history(),
      drawSelection(),
      rectangularSelection(),
      indentOnInput(),
      bracketMatching(),
      closeBrackets(),
      autocompletion({ activateOnTyping: true, icons: false }),
      highlightSelectionMatches(),
      EditorView.lineWrapping,
      syntaxHighlighting(highlightStyle),
      editorTheme,
      placeholderExt(placeholder),
      EditorView.contentAttributes.of({ 'aria-label': ariaLabel }),
      languageCompartment.of(sql({ dialect: dialectFor(technology), upperCaseKeywords: true })),
      readOnlyCompartment.of([EditorState.readOnly.of(readOnly), EditorView.editable.of(!readOnly)]),
      keymap.of([
        {
          key: 'Mod-Enter',
          preventDefault: true,
          run: () => {
            onRunRef.current?.();
            return true;
          },
        },
        ...closeBracketsKeymap,
        ...defaultKeymap,
        ...historyKeymap,
        ...completionKeymap,
        ...searchKeymap,
        indentWithTab,
      ]),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) onChangeRef.current?.(update.state.doc.toString());
      }),
    ];

    view.current = new EditorView({
      state: EditorState.create({ doc: value, extensions }),
      parent: host.current,
    });

    return () => {
      view.current?.destroy();
      view.current = null;
    };
    // The editor is created once; every prop below is pushed in via effects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Push external value changes in without clobbering local edits or the cursor.
  useEffect(() => {
    const editor = view.current;
    if (!editor) return;
    const current = editor.state.doc.toString();
    if (current === value) return;
    editor.dispatch({
      changes: { from: 0, to: current.length, insert: value },
      selection: { anchor: Math.min(editor.state.selection.main.anchor, value.length) },
    });
  }, [value]);

  useEffect(() => {
    view.current?.dispatch({
      effects: readOnlyCompartment.reconfigure([
        EditorState.readOnly.of(readOnly),
        EditorView.editable.of(!readOnly),
      ]),
    });
  }, [readOnly, readOnlyCompartment]);

  useEffect(() => {
    view.current?.dispatch({
      effects: languageCompartment.reconfigure(
        sql({ dialect: dialectFor(technology), upperCaseKeywords: true }),
      ),
    });
  }, [technology, languageCompartment]);

  return <div ref={host} className={cn('h-full min-h-0 overflow-hidden', className)} />;
};
