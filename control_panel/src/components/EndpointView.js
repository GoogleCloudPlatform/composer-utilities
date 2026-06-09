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

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiSections } from '../apiEndpoints';
import { Badge, Card, Form, Button, Alert, Table, Spinner, Dropdown } from 'react-bootstrap';
import apiClient from '../api/axios';
import { useEnvironment } from '../context/EnvironmentContext';

function EndpointView() {
  const { endpointId } = useParams();
  const { currentEnvironment } = useEnvironment();

  const extractLineNumber = (stackTrace, fullFilename) => {
    if (!stackTrace) return null;

    // Regex to capture: File "...", line X
    const regex = /File ["'](.*?)["'], line (\d+)/g;
    let match;
    let lastLine = null;
    let targetLine = null;

    // Use basename for matching if full filename is provided
    const basename = fullFilename ? fullFilename.split('/').pop() : null;

    while ((match = regex.exec(stackTrace)) !== null) {
      const file = match[1];
      const line = match[2];

      // Update last seen line (fallback)
      lastLine = line;

      // Check if this file matches our DAG
      if (basename && file.endsWith(basename)) {
        targetLine = line;
      }
    }

    // If specific file found, use it. Otherwise use the last line number found in the entire trace.
    const finalLine = targetLine || lastLine;



    return finalLine;
  };
  const [endpoint, setEndpoint] = useState(null);
  const [pathParams, setPathParams] = useState({});
  const [queryParams, setQueryParams] = useState({});
  const [body, setBody] = useState('');
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [dags, setDags] = useState([]);
  const [selectedDags, setSelectedDags] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);
  const [importErrors, setImportErrors] = useState([]);
  const [filter, setFilter] = useState('');
  const [showErrorDagsOnly, setShowErrorDagsOnly] = useState(false);
  const [columnFilters, setColumnFilters] = useState({});

  const fetchDags = useCallback(async () => {
    if (!currentEnvironment) return;
    setIsLoading(true);
    setError(null);
    try {
      if (currentEnvironment.url === 'all') {
        const response = await apiClient.get('/api/all-dags');
        setDags(response.data.dags);
        setImportErrors(response.data.import_errors || []);
      } else {
        const dagsResponse = await apiClient.get('/api/v1/dags', { headers: { 'X-Composer-Environment': currentEnvironment.url } });
        const detailsResponse = await apiClient.get(`/api/environments/${currentEnvironment.name}/details`, { headers: { 'X-Composer-Environment': currentEnvironment.url } });
        const importErrorsResponse = await apiClient.get('/api/v1/importErrors', { headers: { 'X-Composer-Environment': currentEnvironment.url } });

        const bucket = detailsResponse.data.config.dagGcsPrefix.split('/')[2];
        const dags = dagsResponse.data.dags.map(dag => ({ ...dag, environment: currentEnvironment, bucket: bucket }));
        const errors = importErrorsResponse.data.import_errors.map(error => ({ ...error, environment: currentEnvironment }));

        setDags(dags);
        setImportErrors(errors);
      }
    } catch (err) {
      setError(err.response || err.message);
    } finally {
      setIsLoading(false);
    }
  }, [currentEnvironment]);

  useEffect(() => {
    if (!currentEnvironment) return;

    const findEndpoint = () => {
      for (const section of apiSections) {
        const found = section.endpoints.find(e => e.id === endpointId);
        if (found) {
          setEndpoint(found);
          // Reset state on endpoint change
          setPathParams({});
          setQueryParams({});
          setBody(found.body ? JSON.stringify(found.body.schema, null, 2) : '');
          setResponse(null);
          setError(null);
          if (found.id === 'get-dags') {
            fetchDags();
          }
          return;
        }
      }
    };
    findEndpoint();
  }, [endpointId, currentEnvironment, fetchDags]);

  const handleParamChange = (setter) => (e) => {
    setter(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const toggleAllDagsPaused = async (isPaused) => {
    try {
      const environmentsResponse = await apiClient.get('/api/environments');
      const environments = environmentsResponse.data;
      const promises = environments.map(env => toggleDagPaused('~', isPaused, env.url));
      await Promise.all(promises);
    } catch (err) {
      setError(err.response || err.message);
    }
  };

  const toggleDagPaused = async (dagId, isPaused, environmentUrl) => {
    let requestUrl = '/api/v1/dags';
    const queryParams = 'update_mask=is_paused';

    if (dagId === '~') {
      requestUrl = `${requestUrl}?dag_id_pattern=%7e&${queryParams}`;
    } else {
      requestUrl = `${requestUrl}/${dagId}?${queryParams}`;
    }

    try {
      await apiClient.patch(requestUrl, { is_paused: isPaused }, { headers: { 'X-Composer-Environment': environmentUrl } });
    } catch (err) {
      setError(err.response || err.message);
    }
  };

  const triggerDag = async (dagId, environmentUrl) => {
    try {
      setIsLoading(true);
      const requestUrl = `/api/v1/dags/${dagId}/dagRuns`;
      const response = await apiClient.post(requestUrl, {}, { headers: { 'X-Composer-Environment': environmentUrl } });
      setResponse(response);
      setError(null);
    } catch (err) {
      setError(err.response || err.message);
      setResponse(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectAllDags = (e) => {
    if (e.target.checked) {
      const allDagIds = dags.map(dag => ({ dag_id: dag.dag_id, env: dag.environment.name }));
      setSelectedDags(allDagIds);
    } else {
      setSelectedDags([]);
    }
  };

  const handleSelectDag = (e, dagId, env) => {
    const dagIdentifier = { dag_id: dagId, env: env };
    if (e.target.checked) {
      setSelectedDags(prev => [...prev, dagIdentifier]);
    } else {
      setSelectedDags(prev => prev.filter(d => d.dag_id !== dagId || d.env !== env));
    }
  };

  const handlePauseSelectedDags = async () => {
    setIsBulkUpdating(true);
    try {
      const promises = selectedDags.map(selectedDag => {
        const dag = dags.find(d => d.dag_id === selectedDag.dag_id && d.environment.name === selectedDag.env);
        return toggleDagPaused(selectedDag.dag_id, true, dag.environment.url);
      });
      await Promise.all(promises);
      setSelectedDags([]);
      fetchDags();
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const handleUnpauseSelectedDags = async () => {
    setIsBulkUpdating(true);
    try {
      const promises = selectedDags.map(selectedDag => {
        const dag = dags.find(d => d.dag_id === selectedDag.dag_id && d.environment.name === selectedDag.env);
        return toggleDagPaused(selectedDag.dag_id, false, dag.environment.url);
      });
      await Promise.all(promises);
      setSelectedDags([]);
      fetchDags();
    } finally {
      setIsBulkUpdating(false);
    }
  };

  // Compute displayed items on every render
  const unassociatedErrors = importErrors.filter(error => {
    return !dags.some(dag => {
      const envMatches = (!dag.environment || !error.environment || (dag.environment.name === error.environment.name && dag.environment.project === error.environment.project));
      const fileMatches = error.filename === dag.fileloc || (dag.file_token && error.filename.endsWith(dag.file_token)) || dag.fileloc.includes(error.filename);
      return envMatches && fileMatches;
    });
  });

  const errorItems = unassociatedErrors.map(error => ({
    is_broken: true,
    dag_id: `Import Error: ${error.filename.split('/').pop()}`,
    environment: error.environment,
    is_paused: null,
    schedule_interval: { value: 'N/A' },
    owners: ['Error'],
    tags: [],
    next_dagrun: 'N/A',
    last_parsed_time: error.timestamp,
    fileloc: error.filename,
    bucket: 'N/A',
    error_details: error
  }));

  const allItems = [...errorItems, ...dags];

  const getUniqueValues = (columnKey) => {
    const values = new Set();
    allItems.forEach(item => {
      let val;
      switch (columnKey) {
        case 'project': val = item.environment?.project; break;
        case 'environment': val = item.environment?.name; break;
        case 'is_paused': val = item.is_paused != null ? item.is_paused.toString() : ''; break;
        case 'schedule_interval': val = item.schedule_interval?.value; break;
        case 'owners': (item.owners || []).forEach(o => values.add(o)); return;
        case 'tags': (item.tags || []).forEach(t => values.add(typeof t === 'object' ? t.name : t)); return;
        default: val = item[columnKey];
      }
      if (val !== undefined && val !== null && val !== '') {
        values.add(val);
      }
    });
    return Array.from(values).sort();
  };

  const renderHeaderWithFilter = (label, columnKey) => {
    const uniqueValues = getUniqueValues(columnKey);
    const selectedValues = columnFilters[columnKey] || [];

    const handleCheckboxChange = (value) => {
      setColumnFilters(prev => {
        const current = prev[columnKey] || [];
        if (current.includes(value)) {
          return { ...prev, [columnKey]: current.filter(v => v !== value) };
        } else {
          return { ...prev, [columnKey]: [...current, value] };
        }
      });
    };

    return (
      <th>
        <div className="d-flex align-items-center justify-content-between">
          <span>{label}</span>
          <Dropdown align="end">
            <Dropdown.Toggle variant="link" id={`dropdown-${columnKey}`} className="p-0 text-decoration-none text-reset ms-1">
              ▼
            </Dropdown.Toggle>
            <Dropdown.Menu style={{ maxHeight: '200px', overflowY: 'auto' }}>
              {uniqueValues.map(value => (
                <Dropdown.Item key={value} as="div" onClick={(e) => e.stopPropagation()}>
                  <Form.Check
                    type="checkbox"
                    id={`check-${columnKey}-${value}`}
                    label={value}
                    checked={selectedValues.includes(value)}
                    onChange={() => handleCheckboxChange(value)}
                  />
                </Dropdown.Item>
              ))}
              {selectedValues.length > 0 && (
                <>
                  <Dropdown.Divider />
                  <Dropdown.Item onClick={() => setColumnFilters(prev => {
                    const newFilters = { ...prev };
                    delete newFilters[columnKey];
                    return newFilters;
                  })}>
                    Clear
                  </Dropdown.Item>
                </>
              )}
            </Dropdown.Menu>
          </Dropdown>
        </div>
      </th>
    );
  };

  let displayedItems = allItems;

  if (showErrorDagsOnly) {
    displayedItems = displayedItems.filter(item => {
      if (item.is_broken) return true; // Always show broken ones when filtering for errors
      return importErrors.some(error => {
        const envMatches = (!item.environment || !error.environment || item.environment.name === error.environment.name);
        const fileMatches = error.filename === item.fileloc || (item.file_token && error.filename.endsWith(item.file_token)) || item.fileloc.includes(error.filename);
        return envMatches && fileMatches;
      });
    });
  }

  if (filter) {
    displayedItems = displayedItems.filter(item =>
      [
        item.dag_id,
        item.description,
        item.environment?.project,
        item.environment?.name,
        item.is_paused?.toString(),
        item.schedule_interval?.value,
        item.owners?.join(', '),
        item.tags?.map(t => typeof t === 'object' ? t.name : t).join(', '),
        item.next_dagrun,
        item.last_parsed_time,
        item.fileloc
      ].some(field =>
        field && field.toString().toLowerCase().includes(filter.toLowerCase())
      )
    );
  }

  // Apply column filters
  displayedItems = displayedItems.filter(item => {
    for (const columnKey in columnFilters) {
      const selectedValues = columnFilters[columnKey];
      if (!selectedValues || selectedValues.length === 0) continue;

      let itemValue;
      switch (columnKey) {
        case 'project': itemValue = item.environment?.project; break;
        case 'environment': itemValue = item.environment?.name; break;
        case 'is_paused': itemValue = item.is_paused != null ? item.is_paused.toString() : ''; break;
        case 'schedule_interval': itemValue = item.schedule_interval?.value; break;
        case 'owners':
          const owners = item.owners || [];
          if (!selectedValues.some(val => owners.includes(val))) return false;
          continue;
        case 'tags':
          const tags = (item.tags || []).map(t => typeof t === 'object' ? t.name : t);
          if (!selectedValues.some(val => tags.includes(val))) return false;
          continue;
        default: itemValue = item[columnKey];
      }

      if (!selectedValues.includes(itemValue)) {
        return false;
      }
    }
    return true;
  });

  const handleSubmit = async () => {
    if (!endpoint) return;

    let finalPath = endpoint.path;
    for (const key in pathParams) {
      finalPath = finalPath.replace(`{${key}}`, pathParams[key]);
    }

    const requestUrl = finalPath;

    try {
      const config = {
        method: endpoint.method,
        url: requestUrl,
        params: queryParams,
        headers: {
          'X-Composer-Environment': currentEnvironment.url,
        },
      };

      if (endpoint.body && body) {
        config.data = JSON.parse(body);
      }

      const result = await apiClient(config);
      setResponse(result);
      if (endpoint.id === 'get-dags') {
        if (result.data.dags) {
          setDags(result.data.dags);
        }
        if (result.data.import_errors) {
          setImportErrors(result.data.import_errors);
        }
      }
      setError(null);
    } catch (err) {
      setError(err.response || err.message);
      setResponse(null);
    }
  };

  if (!endpoint) {
    return <div>Select an endpoint from the sidebar.</div>;
  }

  const getBadgeVariant = (method) => {
    switch (method.toUpperCase()) {
      case 'GET': return 'success';
      case 'POST': return 'primary';
      case 'PATCH': return 'warning';
      case 'DELETE': return 'danger';
      default: return 'secondary';
    }
  };

  if (endpoint.id === 'get-dags') {
    return (
      <Card>
        <Card.Header>
          <h4>
            <Badge bg={getBadgeVariant(endpoint.method)} className="me-2">{endpoint.method}</Badge>
            {endpoint.path}
          </h4>
          <p className="mb-0">{endpoint.description}</p>
        </Card.Header>
        <Card.Body>


          <Button variant="primary" onClick={fetchDags} className="mb-3">Refresh DAGs</Button>
          <div className="mb-3">
            <Button variant="warning" onClick={() => {
              if (currentEnvironment.url === 'all') {
                toggleAllDagsPaused(true);
              } else {
                toggleDagPaused('~', true, currentEnvironment.url);
              }
            }} className="me-2">Pause All DAGs</Button>
            <Button variant="success" onClick={() => {
              if (currentEnvironment.url === 'all') {
                toggleAllDagsPaused(false);
              } else {
                toggleDagPaused('~', false, currentEnvironment.url);
              }
            }}>Unpause All DAGs</Button>
          </div>
          <div className="mb-3 d-flex align-items-center">
            <Button variant="warning" onClick={handlePauseSelectedDags} className="me-2" disabled={selectedDags.length === 0 || isBulkUpdating}>Pause Selected</Button>
            <Button variant="success" onClick={handleUnpauseSelectedDags} disabled={selectedDags.length === 0 || isBulkUpdating}>Unpause Selected</Button>
            {isBulkUpdating && <Spinner animation="border" size="sm" className="ms-2" />}
          </div>
          {isLoading ? (
            <div className="d-flex justify-content-center my-5">
              <Spinner animation="border" role="status">
                <span className="visually-hidden">Loading...</span>
              </Spinner>
            </div>
          ) : (
            <>
              <div className="d-flex mb-2 gap-2 align-items-center">
                <Form.Control
                  type="text"
                  placeholder="Filter DAGs..."
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  className="flex-grow-1"
                />
                <Button
                  variant={showErrorDagsOnly ? "danger" : "outline-danger"}
                  onClick={() => setShowErrorDagsOnly(!showErrorDagsOnly)}
                  title={showErrorDagsOnly ? "Show All DAGs" : "Filter to DAGs with errors"}
                  className="text-nowrap"
                >
                  {showErrorDagsOnly ? "Show All DAGs" : "Show Errors Only"}
                </Button>
                <Button
                  variant="outline-secondary"
                  onClick={() => setColumnFilters({})}
                  disabled={Object.keys(columnFilters).length === 0}
                  title="Clear all column filters"
                  className="text-nowrap"
                >
                  Clear Filters
                </Button>
              </div>
              <div className="text-muted mt-1 mb-3">Showing {displayedItems.length} DAGs</div>
              <Table striped bordered hover key={filter}>
                <thead>
                  <tr>
                    <th><Form.Check type="checkbox" onChange={handleSelectAllDags} /></th>
                    <th>DAG ID</th>
                    {renderHeaderWithFilter('Project', 'project')}
                    {renderHeaderWithFilter('Environment', 'environment')}
                    {renderHeaderWithFilter('Paused', 'is_paused')}
                    {renderHeaderWithFilter('Schedule', 'schedule_interval')}
                    {renderHeaderWithFilter('Owners', 'owners')}
                    {renderHeaderWithFilter('Tags', 'tags')}
                    <th>Next DAG Run</th>
                    <th>Last Parsed</th>
                    <th>DAG File</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedItems.map(item => {
                      if (item.is_broken) {
                        return (
                          <tr key={`error-${item.environment ? `${item.environment.project}-${item.environment.name}` : 'unknown'}-${item.fileloc}-${item.error_details.timestamp}`} className="table-danger">
                            <td><Form.Check type="checkbox" disabled /></td>
                            <td>
                              {item.dag_id}
                              <Badge
                                bg="danger"
                                className="ms-2"
                                style={{ cursor: 'pointer' }}
                                onClick={() => alert(`Import Error:\n${item.error_details.stack_trace}`)}
                                title={item.error_details.stack_trace}
                              >
                                Error
                              </Badge>
                            </td>
                            <td>{item.environment ? item.environment.project : 'Unknown'}</td>
                            <td>{item.environment ? item.environment.name : 'Unknown'}</td>
                            <td>N/A</td>
                            <td>N/A</td>
                            <td>Error</td>
                            <td></td>
                            <td>N/A</td>
                            <td>{item.last_parsed_time}</td>
                            <td>{item.fileloc}</td>
                            <td>
                              <Button variant="danger" size="sm" onClick={() => alert(item.error_details.stack_trace)}>View Trace</Button>
                              <Link to={`/edit-dag/${encodeURIComponent(item.dag_id)}/${item.environment ? item.environment.project : 'unknown'}/${item.environment ? item.environment.name : 'unknown'}?filename=${encodeURIComponent(item.fileloc)}&line=${extractLineNumber(item.error_details.stack_trace, item.fileloc)}`} className="btn btn-info btn-sm ms-2">Edit</Link>
                            </td>
                          </tr>
                        );
                      }

                      const dag = item;
                      const cloudStorageUrl = `https://console.cloud.google.com/storage/browser/_details/${dag.bucket}/dags/${dag.dag_id}.py`;
                      const associatedError = importErrors.find(error => {
                        const envMatches = (!dag.environment || !error.environment || (dag.environment.name === error.environment.name && dag.environment.project === error.environment.project));
                        const fileMatches = error.filename === dag.fileloc || (dag.file_token && error.filename.endsWith(dag.file_token)) || dag.fileloc.includes(error.filename);
                        return envMatches && fileMatches;
                      });

                      return (
                        <tr key={`${dag.environment.project}-${dag.environment.name}-${dag.dag_id}`}>
                          <td><Form.Check type="checkbox" checked={selectedDags.some(d => d.dag_id === dag.dag_id && d.env === dag.environment.name)} onChange={(e) => handleSelectDag(e, dag.dag_id, dag.environment.name)} /></td>
                          <td>
                            {dag.dag_id}
                            {associatedError && (
                              <Badge
                                bg="danger"
                                className="ms-2"
                                style={{ cursor: 'pointer' }}
                                onClick={() => alert(`Import Error:\n${associatedError.stack_trace}`)}
                                title={associatedError.stack_trace}
                              >
                                Import Error
                              </Badge>
                            )}
                          </td>
                          <td>{dag.environment.project}</td>
                          <td>{dag.environment.name}</td>
                          <td>{dag.is_paused.toString()}</td>
                          <td>{dag.schedule_interval?.value}</td>
                          <td>{dag.owners?.join(', ')}</td>
                          <td>{dag.tags?.map(tag => typeof tag === 'object' ? tag.name : tag).join(', ')}</td>
                          <td>{dag.next_dagrun}</td>
                          <td>{dag.last_parsed_time}</td>
                          <td><a href={cloudStorageUrl} target="_blank" rel="noopener noreferrer">{`${dag.dag_id}.py`}</a></td>
                          <td>
                            {!associatedError && (
                              <>
                                <Button
                                  variant="warning"
                                  size="sm"
                                  onClick={async () => {
                                    await toggleDagPaused(dag.dag_id, true, dag.environment.url);
                                    fetchDags();
                                  }}
                                  disabled={dag.is_paused}
                                  className="me-2"
                                >
                                  Pause
                                </Button>
                                <Button
                                  variant="success"
                                  size="sm"
                                  onClick={async () => {
                                    await toggleDagPaused(dag.dag_id, false, dag.environment.url);
                                    fetchDags();
                                  }}
                                  disabled={!dag.is_paused}
                                  className="me-2"
                                >
                                  Unpause
                                </Button>
                                <Button
                                  variant="primary"
                                  size="sm"
                                  onClick={() => triggerDag(dag.dag_id, dag.environment.url)}
                                  className="me-2"
                                  title="Trigger DAG"
                                >
                                  Trigger
                                </Button>
                              </>
                            )}
                            <Link to={`/edit-dag/${dag.dag_id}/${dag.environment.project}/${dag.environment.name}?filename=${encodeURIComponent(dag.fileloc)}${associatedError ? `&line=${extractLineNumber(associatedError.stack_trace, dag.fileloc)}` : ''}`} className="btn btn-info btn-sm">Edit</Link>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </Table>
            </>
          )}
        </Card.Body>
        {(response || error) && (
          <Card.Footer>
            <h5>Response</h5>
            {response && (
              <>
                <Alert variant="success">
                  <strong>Status: {response.status} {response.statusText}</strong>
                </Alert>
                <pre>{JSON.stringify(response.data, null, 2)}</pre>
              </>
            )}
            {error && (
              <>
                <Alert variant="danger">
                  <strong>Error: {error.status ? `${error.status} ${error.statusText}` : error}</strong>
                </Alert>
                {error.data && <pre>{JSON.stringify(error.data, null, 2)}</pre>}
              </>
            )}
          </Card.Footer>
        )}
      </Card>
    );
  }

  return (
    <Card>
      <Card.Header>
        <h4>
          <Badge bg={getBadgeVariant(endpoint.method)} className="me-2">{endpoint.method}</Badge>
          {endpoint.path}
        </h4>
        <p className="mb-0">{endpoint.description}</p>
      </Card.Header>

      <Card.Body>
        {endpoint.parameters.path.length > 0 && (
          <>
            <h5>Path Parameters</h5>
            {endpoint.parameters.path.map(p => (
              <Form.Group className="mb-3" key={p.name}>
                <Form.Label>{p.name} <span className="text-muted">({p.type})</span></Form.Label>
                <Form.Control
                  type="text"
                  name={p.name}
                  placeholder={p.description}
                  onChange={handleParamChange(setPathParams)}
                />
              </Form.Group>
            ))}
          </>
        )}

        {endpoint.parameters.query.length > 0 && (
          <>
            <h5>Query Parameters</h5>
            {endpoint.parameters.query.map(p => (
              <Form.Group className="mb-3" key={p.name}>
                <Form.Label>{p.name} <span className="text-muted">({p.type})</span></Form.Label>
                <Form.Control
                  type="text"
                  name={p.name}
                  placeholder={p.description}
                  onChange={handleParamChange(setQueryParams)}
                />
              </Form.Group>
            ))}
          </>
        )}

        {endpoint.body && (
          <>
            <h5>Request Body</h5>
            <Form.Group className="mb-3">
              <Form.Label><Badge bg="secondary">{endpoint.body.type}</Badge></Form.Label>
              <Form.Control
                as="textarea"
                rows={10}
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
            </Form.Group>
          </>
        )}

        <Button variant="primary" onClick={handleSubmit} disabled={currentEnvironment && currentEnvironment.url === 'all'}>Send Request</Button>
      </Card.Body>

      {(response || error) && (
        <Card.Footer>
          <h5>Response</h5>
          {response && (
            <>
              <Alert variant="success">
                <strong>Status: {response.status} {response.statusText}</strong>
              </Alert>
              {endpoint.id === 'get-dag-runs' && response.data.dag_runs ? (
                <Table striped bordered hover>
                  <thead>
                    <tr>
                      <th>DAG Run ID</th>
                      <th>State</th>
                      <th>Execution Date</th>
                      <th>Start Date</th>
                      <th>End Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.data.dag_runs.map(run => (
                      <tr key={run.dag_run_id}>
                        <td>{run.dag_run_id}</td>
                        <td>{run.state}</td>
                        <td>{run.execution_date}</td>
                        <td>{run.start_date}</td>
                        <td>{run.end_date}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <pre>{JSON.stringify(response.data, null, 2)}</pre>
              )}
            </>
          )}
          {error && (
            <>
              <Alert variant="danger">
                <strong>Error: {error.status ? `${error.status} ${error.statusText}` : error}</strong>
              </Alert>
              {error.data && <pre>{JSON.stringify(error.data, null, 2)}</pre>}
            </>
          )}
        </Card.Footer>
      )}
    </Card>
  );
}

export default EndpointView;