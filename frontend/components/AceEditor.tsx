
import React, { useEffect, useRef } from 'react';

interface AceEditorProps {
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  height?: string;
  enableAutocomplete?: boolean;
}

const AceEditor: React.FC<AceEditorProps> = ({ 
  value, 
  onChange, 
  readOnly = false, 
  height = '400px',
  enableAutocomplete = true 
}) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const editorInstance = useRef<any>(null);

  useEffect(() => {
    if (editorRef.current && !editorInstance.current) {
      const ace = (window as any).ace;
      if (!ace) {
        console.error('Ace editor script not found in window');
        return;
      }

      // Crucial: Fix "Unable to infer path to ace"
      ace.config.set('basePath', 'https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.12/');
      
      // Load language tools if available
      try {
        ace.require("ace/ext/language_tools");
      } catch (e) {
        console.debug("Language tools initialization skipped");
      }

      editorInstance.current = ace.edit(editorRef.current);
      editorInstance.current.setTheme("ace/theme/dracula");
      editorInstance.current.session.setMode("ace/mode/sql");
      
      editorInstance.current.setOptions({
        enableBasicAutocompletion: enableAutocomplete,
        enableLiveAutocompletion: enableAutocomplete,
        enableSnippets: true,
        showLineNumbers: true,
        tabSize: 2,
        wrap: true,
        fontSize: '14px',
        showPrintMargin: false,
        highlightActiveLine: !readOnly,
        useWorker: false // Prevents cross-origin issues with CDN
      });

      editorInstance.current.on("change", () => {
        if (onChange) {
          const val = editorInstance.current.getValue();
          onChange(val);
        }
      });
    }

    return () => {
      if (editorInstance.current) {
        // Cleanup if needed
      }
    };
  }, []);

  useEffect(() => {
    if (editorInstance.current) {
      const safeValue = value || ''; 
      if (editorInstance.current.getValue() !== safeValue) {
        editorInstance.current.setValue(safeValue, -1);
      }
      editorInstance.current.setReadOnly(readOnly);
    }
  }, [value, readOnly]);

  return <div ref={editorRef} style={{ height, width: '100%' }} className="rounded-lg border border-gray-800 shadow-2xl overflow-hidden" />;
};

export default AceEditor;
