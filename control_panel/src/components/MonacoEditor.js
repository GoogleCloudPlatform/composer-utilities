/*
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

import React, { useEffect, useRef } from 'react';

function MonacoEditor({ value, onChange, language = 'python', theme = 'vs-dark', errorLine, readOnly = false }) {
  const containerRef = useRef(null);
  const editorRef = useRef(null);
  const decorationsRef = useRef([]);

  useEffect(() => {
    // If monaco is already loaded on window, initialize immediately
    if (window.monaco) {
      initMonaco();
      return;
    }

    // Load Monaco loader script dynamically from CDN
    let loaderScript = document.getElementById('monaco-loader');
    if (!loaderScript) {
      loaderScript = document.createElement('script');
      loaderScript.id = 'monaco-loader';
      loaderScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs/loader.js';
      loaderScript.async = true;
      document.body.appendChild(loaderScript);
    }

    const checkAndInit = () => {
      if (window.require) {
        window.require.config({
          paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' }
        });
        window.require(['vs/editor/editor.main'], () => {
          initMonaco();
        });
      } else {
        setTimeout(checkAndInit, 50);
      }
    };

    loaderScript.addEventListener('load', checkAndInit);

    return () => {
      loaderScript.removeEventListener('load', checkAndInit);
      if (editorRef.current) {
        editorRef.current.dispose();
      }
    };

    function initMonaco() {
      if (!containerRef.current || editorRef.current) return;

      const editor = window.monaco.editor.create(containerRef.current, {
        value: value,
        language: language,
        theme: theme,
        readOnly: readOnly,
        automaticLayout: true,
        minimap: { enabled: true },
        fontSize: 14,
        lineHeight: 22,
        scrollBeyondLastLine: false,
        glyphMargin: true, // Show margin for error glyphs
      });

      editorRef.current = editor;

      editor.onDidChangeModelContent(() => {
        const newValue = editor.getValue();
        if (onChange) {
          onChange(newValue);
        }
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update editor value if it changes from props externally
  useEffect(() => {
    if (editorRef.current && value !== editorRef.current.getValue()) {
      editorRef.current.setValue(value || '');
    }
  }, [value]);

  // Update readOnly setting if it changes
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.updateOptions({ readOnly });
    }
  }, [readOnly]);

  // Update theme setting if it changes
  useEffect(() => {
    if (window.monaco) {
      window.monaco.editor.setTheme(theme);
    }
  }, [theme]);

  // Handle highlighting the error line
  useEffect(() => {
    if (editorRef.current && window.monaco) {
      const editor = editorRef.current;
      const line = parseInt(errorLine, 10);
      if (line > 0) {
        // Clear previous decorations
        decorationsRef.current = editor.deltaDecorations(decorationsRef.current, []);

        // Add new error decoration
        decorationsRef.current = editor.deltaDecorations([], [
          {
            range: new window.monaco.Range(line, 1, line, 1),
            options: {
              isWholeLine: true,
              className: 'error-line-highlight',
              glyphMarginClassName: 'error-glyph-margin',
              glyphMarginHoverMessage: { value: 'Syntax/Import Error Line' }
            },
          },
        ]);

        // Reveal and center the error line
        editor.revealLineInCenter(line);
      } else {
        // Clear decorations if errorLine is not positive
        decorationsRef.current = editor.deltaDecorations(decorationsRef.current, []);
      }
    }
  }, [errorLine, value]);

  return (
    <div
      ref={containerRef}
      style={{
        height: '600px',
        border: '1px solid #ced4da',
        borderRadius: '4px',
        overflow: 'hidden'
      }}
    />
  );
}

export default MonacoEditor;
