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

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Card, Form, Button, Alert } from 'react-bootstrap';
import apiClient from '../api/axios';
import MonacoEditor from './MonacoEditor';
import { useTheme } from '../context/ThemeContext';

function DagEditView() {
  const { dagId, project, env } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const filename = searchParams.get('filename');
  const errorLine = searchParams.get('line');
  const [content, setContent] = useState('');
  const [tags, setTags] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [environments, setEnvironments] = useState([]);
  const [highlightedLine, setHighlightedLine] = useState(errorLine);
  const { theme } = useTheme();

  useEffect(() => {
    setHighlightedLine(errorLine);
  }, [errorLine]);

  useEffect(() => {
    const fetchEnvironments = async () => {
      try {
        const response = await apiClient.get('/api/environments');
        setEnvironments(response.data);
      } catch (err) {
        setError(err.response || err.message);
      }
    };
    fetchEnvironments();
  }, []);

  const composerEnv = environments.find(e => e.name === env && e.project === project);

  useEffect(() => {
    if (!composerEnv) return;
    setContent('');
    const fetchDagContent = async () => {
      try {
        const params = {};
        if (filename) {
          params.filename = filename;
        }
        const response = await apiClient.get(`/api/dags/${dagId}/content`, {
          headers: { 'X-Composer-Environment': composerEnv.url },
          params: params
        });
        setContent(response.data);

        const content = response.data;

        let dagStartIndex = -1;
        let matchType = '';

        if (content.indexOf('@dag(') !== -1) {
          dagStartIndex = content.indexOf('@dag(');
          matchType = '@dag(';
        } else if (content.indexOf('with DAG(') !== -1) {
          dagStartIndex = content.indexOf('with DAG(');
          matchType = 'with DAG(';
        } else if (content.indexOf('DAG(') !== -1) {
          dagStartIndex = content.indexOf('DAG(');
          matchType = 'DAG(';
        }

        if (dagStartIndex === -1) {
            setTags('');
            return;
        }

        let openParens = 1;
        let dagEndIndex = -1;

        const searchStart = dagStartIndex + matchType.length;

        for (let i = searchStart; i < content.length; i++) {
            if (content[i] === '(') {
                openParens++;
            } else if (content[i] === ')') {
                openParens--;
            }
            if (openParens === 0) {
                dagEndIndex = i;
                break;
            }
        }

        if (dagEndIndex !== -1) {
            const dagDefinition = content.substring(dagStartIndex, dagEndIndex + 1);
            const tagsRegex = /tags=\[(.*?)\]/;
            const tagsMatch = dagDefinition.match(tagsRegex);
            if (tagsMatch && tagsMatch[1]) {
                setTags(tagsMatch[1].replace(/['"]/g, ''));
            } else {
                setTags('');
            }
        } else {
            setTags('');
        }

      } catch (err) {
        setError(err.response || err.message);
      }
    };
    fetchDagContent();
  }, [dagId, composerEnv, filename]);

  // Scrolling and error highlighting are handled natively by MonacoEditor

  const handleSave = async () => {
    if (!composerEnv) return;

    const newTags = tags.split(',').map(t => `'${t.trim()}'`).join(', ');
    const newTagsLine = `tags=[${newTags}]`;

    let newContent = content;

    // Find the DAG definition (could be @dag(, with DAG(, or DAG()
    let dagStartIndex = -1;
    let matchType = '';

    if (newContent.indexOf('@dag(') !== -1) {
      dagStartIndex = newContent.indexOf('@dag(');
      matchType = '@dag(';
    } else if (newContent.indexOf('with DAG(') !== -1) {
      dagStartIndex = newContent.indexOf('with DAG(');
      matchType = 'with DAG(';
    } else if (newContent.indexOf('DAG(') !== -1) {
      dagStartIndex = newContent.indexOf('DAG(');
      matchType = 'DAG(';
    }

    if (dagStartIndex !== -1) {
      let openParens = 1;
      let dagEndIndex = -1;

      // Start counting parens after the matched string
      const searchStart = dagStartIndex + matchType.length;

      for (let i = searchStart; i < newContent.length; i++) {
        if (newContent[i] === '(') {
          openParens++;
        } else if (newContent[i] === ')') {
          openParens--;
        }
        if (openParens === 0) {
          dagEndIndex = i;
          break;
        }
      }

      if (dagEndIndex !== -1) {
        const dagDefinition = newContent.substring(dagStartIndex, dagEndIndex + 1);
        let newDagDefinition;

          if (dagDefinition.includes('tags=[')) {
            newDagDefinition = dagDefinition.replace(/tags=\[.*?\]/, newTagsLine);
          } else {
            const insertionPoint = dagDefinition.lastIndexOf(')');
            const dagArgs = dagDefinition.substring(matchType.length, insertionPoint).trim();
            const newDagArgs = dagArgs.endsWith(',') ? `${dagArgs}\n    ${newTagsLine}` : `${dagArgs},\n    ${newTagsLine}`;
            newDagDefinition = `${matchType}${newDagArgs}\n)`;
          }

          newContent = newContent.replace(dagDefinition, newDagDefinition);
      }
    }


    try {
      const params = {};
      if (filename) {
        params.filename = filename;
      }
      await apiClient.post(`/api/dags/${dagId}/content`, { content: newContent }, {
        headers: { 'X-Composer-Environment': composerEnv.url },
        params: params
      });
      setSuccess('DAG content updated successfully.');
      setError(null);
      setHighlightedLine(null);
    } catch (err) {
      if (err.response && err.response.status === 422) {
        const detail = err.response.data.detail;
        setError({
          status: 422,
          statusText: 'Syntax Error',
          data: detail
        });
        if (detail && detail.line) {
          setHighlightedLine(detail.line);
        }
      } else {
        setError(err.response || err.message);
      }
      setSuccess(null);
    }
  };

  return (
    <Card>
      <Card.Header>
        <h4>Editing DAG: {filename ? filename.split('/').pop() : dagId}</h4>
      </Card.Header>
      <Card.Body>
        {!errorLine && (
          <Form.Group className="mb-3">
            <Form.Label>Tags</Form.Label>
            <Form.Control
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="Enter comma-separated tags"
            />
          </Form.Group>
        )}
        <Form.Group className="mb-3">
          <MonacoEditor
            value={content}
            onChange={setContent}
            errorLine={highlightedLine}
            theme={theme === 'dark' ? 'vs-dark' : 'vs-light'}
          />
        </Form.Group>
        <Button variant="primary" onClick={handleSave} className="me-2" disabled={!composerEnv}>Save</Button>
        <Button variant="secondary" onClick={() => navigate('/endpoint/get-dags')}>Back</Button>
      </Card.Body>
      <Card.Footer>
        {success && <Alert variant="success">{success}</Alert>}
        {error && (
          <Alert variant="danger">
            <strong>Error: {error.status ? `${error.status} ${error.statusText}` : error}</strong>
            {error.data && <pre>{JSON.stringify(error.data, null, 2)}</pre>}
          </Alert>
        )}
      </Card.Footer>
    </Card>
  );
}

export default DagEditView;