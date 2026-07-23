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

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { apiSections } from '../apiEndpoints';
import { Badge, Card, Form, Button, Alert, Table, Spinner, Dropdown, Modal } from 'react-bootstrap';
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
  const [showRunningDagsOnly, setShowRunningDagsOnly] = useState(false);
  const [columnFilters, setColumnFilters] = useState({});
  const [showModal, setShowModal] = useState(false);
  const handleCloseModal = () => setShowModal(false);
  const [triggeringDag, setTriggeringDag] = useState(null);
  const [paramValues, setParamValues] = useState({});
  const [showTriggerModal, setShowTriggerModal] = useState(false);
  const [triggeredEnvironment, setTriggeredEnvironment] = useState(null);
  const [showClearMappedModal, setShowClearMappedModal] = useState(false);
  const [clearingMappedDag, setClearingMappedDag] = useState(null);

  const columnsList = [
    { key: 'project', label: 'Project' },
    { key: 'environment', label: 'Environment' },
    { key: 'is_paused', label: 'Paused' },
    { key: 'schedule_interval', label: 'Schedule' },
    { key: 'owners', label: 'Owners' },
    { key: 'tags', label: 'Tags' },
    { key: 'next_dagrun', label: 'Next Run' },
    { key: 'last_parsed_time', label: 'Last Parsed' },
    { key: 'fileloc', label: 'DAG File' }
  ];

  const [visibleColumns, setVisibleColumns] = useState(() => {
    const saved = localStorage.getItem('visibleColumns');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {}
    }
    return {
      project: true,
      environment: true,
      is_paused: true,
      schedule_interval: true,
      owners: true,
      tags: true,
      next_dagrun: true,
      last_parsed_time: true,
      fileloc: true
    };
  });

  useEffect(() => {
    localStorage.setItem('visibleColumns', JSON.stringify(visibleColumns));
  }, [visibleColumns]);

  const toggleColumnVisibility = (key) => {
    setVisibleColumns(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

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
        const apiVersion = currentEnvironment.imageVersion && currentEnvironment.imageVersion.includes('-airflow-3') ? 'v2' : 'v1';
        const dagsResponse = await apiClient.get(`/api/${apiVersion}/dags`, { headers: { 'X-Composer-Environment': currentEnvironment.url } });
        const detailsResponse = await apiClient.get(`/api/environments/${currentEnvironment.name}/details`, { headers: { 'X-Composer-Environment': currentEnvironment.url } });
        const importErrorsResponse = await apiClient.get(`/api/${apiVersion}/importErrors`, { headers: { 'X-Composer-Environment': currentEnvironment.url } });

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

  const handleToggleAllDags = async (isPaused) => {
    setIsBulkUpdating(true);
    try {
      if (currentEnvironment.url === 'all') {
        const environmentsResponse = await apiClient.get('/api/environments');
        const environments = environmentsResponse.data;
        const promises = environments.map(env => toggleDagPaused('~', isPaused, env));
        await Promise.all(promises);
      } else {
        await toggleDagPaused('~', isPaused, currentEnvironment);
      }
      fetchDags();
    } catch (err) {
      setError(err.response || err.message);
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const toggleDagPaused = async (dagId, isPaused, environment) => {
    const apiVersion = environment.imageVersion && environment.imageVersion.includes('-airflow-3') ? 'v2' : 'v1';
    let requestUrl = `/api/${apiVersion}/dags`;
    const queryParams = 'update_mask=is_paused';

    if (dagId === '~') {
      requestUrl = `${requestUrl}?dag_id_pattern=%25&${queryParams}`;
    } else {
      requestUrl = `${requestUrl}/${dagId}?${queryParams}`;
    }

    try {
      await apiClient.patch(requestUrl, { is_paused: isPaused }, { headers: { 'X-Composer-Environment': environment.url } });
      return true;
    } catch (err) {
      setError(err.response || err.message);
      return false;
    }
  };

  const triggerDag = async (dagId, environment, conf = {}) => {
    try {
      const apiVersion = environment.imageVersion && environment.imageVersion.includes('-airflow-3') ? 'v2' : 'v1';
      const requestUrl = `/api/${apiVersion}/dags/${dagId}/dagRuns`;
      const body = apiVersion === 'v2' ? { logical_date: new Date().toISOString(), conf } : { conf };
      const response = await apiClient.post(requestUrl, body, { headers: { 'X-Composer-Environment': environment.url } });
      setTriggeredEnvironment(environment);
      setResponse(response);
      setError(null);
      setShowModal(true);
    } catch (err) {
      setTriggeredEnvironment(null);
      setError(err.response || err.message);
      setResponse(null);
      setShowModal(true);
    }
  };

  const handleTriggerClick = async (dag) => {
    try {
      const apiVersion = dag.environment.imageVersion && dag.environment.imageVersion.includes('-airflow-3') ? 'v2' : 'v1';
      const detailsUrl = `/api/${apiVersion}/dags/${dag.dag_id}/details`;
      const response = await apiClient.get(detailsUrl, { headers: { 'X-Composer-Environment': dag.environment.url } });
      const detailedDag = response.data;
      
      if (detailedDag.params && Object.keys(detailedDag.params).length > 0) {
        const initialValues = {};
        Object.keys(detailedDag.params).forEach(key => {
          const param = detailedDag.params[key];
          initialValues[key] = (param && typeof param === 'object' && 'value' in param) ? param.value : param;
        });
        setParamValues(initialValues);
        setTriggeringDag({ ...dag, params: detailedDag.params });
        setShowTriggerModal(true);
      } else {
        triggerDag(dag.dag_id, dag.environment);
      }
    } catch (err) {
      setError(err.response || err.message);
      setShowModal(true);
    }
  };

  const handleReparseClick = async (dag) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.post(`/api/dags/${dag.dag_id}/reparse`, null, {
        headers: {
          'X-Composer-Environment': dag.environment.url,
        },
        params: {
          filename: dag.fileloc
        }
      });
      setTriggeredEnvironment(dag.environment);
      setResponse(response);
      setError(null);
      setShowModal(true);
    } catch (err) {
      setTriggeredEnvironment(null);
      setError(err.response || err.message);
      setResponse(null);
      setShowModal(true);
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
        return toggleDagPaused(selectedDag.dag_id, true, dag.environment);
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
        return toggleDagPaused(selectedDag.dag_id, false, dag.environment);
      });
      await Promise.all(promises);
      setSelectedDags([]);
      fetchDags();
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const failTasksForDag = async (dag) => {
    let tasksModified = 0;
    const apiVersion = dag.environment.imageVersion && dag.environment.imageVersion.includes('-airflow-3') ? 'v2' : 'v1';
    const encodedDagId = encodeURIComponent(dag.dag_id);
    const activeStates = ['running', 'queued', 'scheduled', 'up_for_retry', 'up_for_reschedule', 'deferred'];
    const stateQuery = activeStates.map(s => `state=${s}`).join('&');
    const tiResponse = await apiClient.get(`/api/${apiVersion}/dags/${encodedDagId}/dagRuns/~/taskInstances?${stateQuery}`, {
      headers: { 'X-Composer-Environment': dag.environment.url }
    });
    
    const activeTasks = tiResponse.data.task_instances || [];
    const patchPromises = [];
    const patchedAirflow3TaskIds = new Set();
    
    for (const task of activeTasks) {
      const encodedDagRunId = encodeURIComponent(task.dag_run_id);
      const encodedTaskId = encodeURIComponent(task.task_id);
      const isMapped = task.map_index !== undefined && task.map_index >= 0;
      
      let patchUrl = `/api/${apiVersion}/dags/${encodedDagId}/dagRuns/${encodedDagRunId}/taskInstances/${encodedTaskId}`;
      
      if (apiVersion === 'v2') {
        // Airflow 3: PATCHing the base task (without map_index) automatically patches ALL map indexes.
        // Sending concurrent PATCH requests (even with map_index) to the same task_id causes concurrency/lock errors.
        // Therefore, we de-duplicate by task_id and send exactly one request.
        const uniqueKey = `${task.dag_run_id}_${task.task_id}`;
        if (patchedAirflow3TaskIds.has(uniqueKey)) {
          tasksModified++; // Still count it for the UI since it will be modified by the single request
          continue;
        }
        patchedAirflow3TaskIds.add(uniqueKey);
        // Do NOT append ?map_index= for Airflow 3
      } else {
        // Airflow 2: Mapped tasks do not have a base task instance, must patch each map index individually.
        // Concurrency is handled correctly by Airflow 2 API.
        if (isMapped) {
          patchUrl += `/${task.map_index}`;
        }
      }
      
      const payload = { new_state: 'failed' };
      if (apiVersion === 'v1') {
        payload.dry_run = false;
      }
      
      patchPromises.push(
        apiClient.patch(patchUrl, payload, { headers: { 'X-Composer-Environment': dag.environment.url } })
      );
      tasksModified++;
    }
    await Promise.all(patchPromises);
    return tasksModified;
  };

  const handleFailRunningTasks = async () => {
    setIsBulkUpdating(true);
    try {
      let totalTasksModified = 0;
      const promises = selectedDags.map(async (selectedDag) => {
        const dag = dags.find(d => d.dag_id === selectedDag.dag_id && d.environment.name === selectedDag.env);
        if (dag) {
          const modified = await failTasksForDag(dag);
          totalTasksModified += modified;
        }
      });
      await Promise.all(promises);
      setSelectedDags([]);
      fetchDags();
      setResponse({
        data: { message: `Successfully executed request. Found and marked ${totalTasksModified} running tasks as failed for selected DAGs.` },
        status: 200,
        statusText: "OK"
      });
      setShowModal(true);
    } catch (err) {
      let errorDetails = err.message;
      if (err.response && err.response.data) {
        errorDetails = typeof err.response.data === 'string' ? err.response.data : JSON.stringify(err.response.data);
      }
      setError(`Error: ${errorDetails}`);
      setShowModal(true);
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const handleFailDagRunningTasks = async (dag) => {
    setIsBulkUpdating(true);
    try {
      const totalTasksModified = await failTasksForDag(dag);
      fetchDags();
      setResponse({
        data: { message: `Successfully executed request. Found and marked ${totalTasksModified} running tasks as failed for DAG ${dag.dag_id}.` },
        status: 200,
        statusText: "OK"
      });
      setShowModal(true);
    } catch (err) {
      let errorDetails = err.message;
      if (err.response && err.response.data) {
        errorDetails = typeof err.response.data === 'string' ? err.response.data : JSON.stringify(err.response.data);
      }
      setError(`Error: ${errorDetails}`);
      setShowModal(true);
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const handleFailRunningDags = async () => {
    setIsBulkUpdating(true);
    try {
      let totalDagRunsModified = 0;
      
      const uniqueEnvironments = [];
      const envUrls = new Set();
      dags.forEach(dag => {
        if (dag.environment && !envUrls.has(dag.environment.url)) {
          envUrls.add(dag.environment.url);
          uniqueEnvironments.push(dag.environment);
        }
      });
      
      const patchPromises = [];
      
      for (const env of uniqueEnvironments) {
        const apiVersion = env.imageVersion && env.imageVersion.includes('-airflow-3') ? 'v2' : 'v1';
        const activeStates = ['running', 'queued'];
        const stateQuery = activeStates.map(s => `state=${s}`).join('&');
        
        const drResponse = await apiClient.get(`/api/${apiVersion}/dags/~/dagRuns?${stateQuery}`, {
          headers: { 'X-Composer-Environment': env.url }
        });
        
        const activeDagRuns = drResponse.data.dag_runs || [];
        
        for (const run of activeDagRuns) {
          totalDagRunsModified++;
          const encodedDagId = encodeURIComponent(run.dag_id);
          const encodedDagRunId = encodeURIComponent(run.dag_run_id);
          const patchUrl = `/api/${apiVersion}/dags/${encodedDagId}/dagRuns/${encodedDagRunId}`;
          const payload = { state: 'failed' };
          
          patchPromises.push(
            apiClient.patch(patchUrl, payload, { headers: { 'X-Composer-Environment': env.url } })
          );
        }
      }
      
      await Promise.all(patchPromises);
      fetchDags();
      
      setResponse({
        data: { message: `Successfully executed request. Found and marked ${totalDagRunsModified} running DAGs as failed.` },
        status: 200,
        statusText: "OK"
      });
      setShowModal(true);
    } catch (err) {
      let errorDetails = err.message;
      if (err.response && err.response.data) {
        errorDetails = typeof err.response.data === 'string' ? err.response.data : JSON.stringify(err.response.data);
      }
      setError(`Error: ${errorDetails}`);
      setShowModal(true);
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const clearTasksForDag = async (dag) => {
    const apiVersion = dag.environment.imageVersion && dag.environment.imageVersion.includes('-airflow-3') ? 'v2' : 'v1';
    const encodedDagId = encodeURIComponent(dag.dag_id);

    // Fetch latest DAG run
    const orderParam = apiVersion === 'v2' ? 'order_by=-logical_date' : 'order_by=-execution_date';
    const dagRunsUrl = `/api/${apiVersion}/dags/${encodedDagId}/dagRuns?${orderParam}&limit=1`;
    let latestRunDate = null;
    let latestRunId = null;
    try {
      const runResponse = await apiClient.get(dagRunsUrl, { headers: { 'X-Composer-Environment': dag.environment.url } });
      if (runResponse.data && runResponse.data.dag_runs && runResponse.data.dag_runs.length > 0) {
        const latestRun = runResponse.data.dag_runs[0];
        latestRunDate = latestRun.logical_date || latestRun.execution_date;
        latestRunId = latestRun.dag_run_id;
      }
    } catch (e) {
      console.error(`Failed to fetch latest run for DAG ${dag.dag_id}`, e);
    }
    
    const requestUrl = `/api/${apiVersion}/dags/${encodedDagId}/clearTaskInstances`;
    
    const payload = { 
      dry_run: false,
      reset_dag_runs: true,
      only_failed: false,
      only_running: false
    }; 
    
    if (apiVersion === 'v2' && latestRunId) {
      payload.dag_run_id = latestRunId;
    } else if (latestRunDate) {
      payload.start_date = latestRunDate;
      payload.end_date = latestRunDate;
    }
    
    if (apiVersion === 'v2') {
      try {
        const tasksResponse = await apiClient.get(`/api/${apiVersion}/dags/${encodedDagId}/tasks`, { headers: { 'X-Composer-Environment': dag.environment.url } });
        if (tasksResponse.data && tasksResponse.data.tasks && tasksResponse.data.tasks.length > 0) {
          payload.task_ids = tasksResponse.data.tasks.map(t => t.task_id);
        } else {
          return 0;
        }
      } catch (e) {
        console.error(`Failed to fetch tasks for DAG ${dag.dag_id}`, e);
      }
    }
    
    try {
      const response = await apiClient.post(requestUrl, payload, { 
        headers: { 'X-Composer-Environment': dag.environment.url },
        timeout: 10000 
      });
      
      if (response.data && response.data.task_instances) {
          return response.data.task_instances.length;
      } else if (response.data && response.data.total_entries) {
          return response.data.total_entries;
      }
      return 1;
    } catch (e) {
      if (e.code === 'ECONNABORTED' || (e.response && e.response.status === 500 && e.response.data && e.response.data.detail && String(e.response.data.detail).includes("ReadTimeout"))) {
        console.warn("Clear task request timed out. Assuming it is processing in the background.", e);
        return 0;
      }
      throw e;
    }
  };

  const handleClearExistingTasks = async () => {
    setIsBulkUpdating(true);
    try {
      let totalTasksCleared = 0;
      
      const promises = dags.map(async (dag) => {
          try {
             totalTasksCleared += await clearTasksForDag(dag);
          } catch (e) {
             console.error(`Failed to clear tasks for DAG ${dag.dag_id}`, e);
          }
      });
      await Promise.all(promises);
      
      fetchDags();
      
      setResponse({
        data: { message: `Successfully executed request. Found and cleared tasks for all DAGs. (Approx ${totalTasksCleared} task instances affected)` },
        status: 200,
        statusText: "OK"
      });
      setShowModal(true);
    } catch (err) {
      let errorDetails = err.message;
      if (err.response && err.response.data) {
        errorDetails = typeof err.response.data === 'string' ? err.response.data : JSON.stringify(err.response.data);
      }
      setError(`Error: ${errorDetails}`);
      setShowModal(true);
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const handleClearExistingTasksSelected = async () => {
    setIsBulkUpdating(true);
    try {
      let totalTasksCleared = 0;
      const promises = selectedDags.map(async (selectedDag) => {
        const dag = dags.find(d => d.dag_id === selectedDag.dag_id && d.environment.name === selectedDag.env);
        if (dag) {
           totalTasksCleared += await clearTasksForDag(dag);
        }
      });
      await Promise.all(promises);
      setSelectedDags([]);
      fetchDags();
      setResponse({
        data: { message: `Successfully executed request. Found and cleared ${totalTasksCleared} tasks for selected DAGs.` },
        status: 200,
        statusText: "OK"
      });
      setShowModal(true);
    } catch (err) {
      let errorDetails = err.message;
      if (err.response && err.response.data) {
        errorDetails = typeof err.response.data === 'string' ? err.response.data : JSON.stringify(err.response.data);
      }
      setError(`Error: ${errorDetails}`);
      setShowModal(true);
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const handleClearDagTasks = async (dag) => {
    setIsBulkUpdating(true);
    try {
      const totalTasksCleared = await clearTasksForDag(dag);
      fetchDags();
      setResponse({
        data: { message: `Successfully executed request. Found and cleared ${totalTasksCleared} tasks for DAG ${dag.dag_id}.` },
        status: 200,
        statusText: "OK"
      });
      setShowModal(true);
    } catch (err) {
      let errorDetails = err.message;
      if (err.response && err.response.data) {
        errorDetails = typeof err.response.data === 'string' ? err.response.data : JSON.stringify(err.response.data);
      }
      setError(`Error: ${errorDetails}`);
      setShowModal(true);
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const handleClearMappedSubmit = async (dag, taskId, mapIndex, clearDownstream) => {
    setIsBulkUpdating(true);
    try {
      const apiVersion = dag.environment.imageVersion && dag.environment.imageVersion.includes('-airflow-3') ? 'v2' : 'v1';
      const encodedDagId = encodeURIComponent(dag.dag_id);

      // 1. Fetch latest DAG run to get dag_run_id
      const orderParam = apiVersion === 'v2' ? 'order_by=-logical_date' : 'order_by=-execution_date';
      const dagRunsUrl = `/api/${apiVersion}/dags/${encodedDagId}/dagRuns?${orderParam}&limit=1`;
      const runResponse = await apiClient.get(dagRunsUrl, { headers: { 'X-Composer-Environment': dag.environment.url } });
      if (!runResponse.data || !runResponse.data.dag_runs || runResponse.data.dag_runs.length === 0) {
        throw new Error("No DAG runs found to clear.");
      }
      const latestRun = runResponse.data.dag_runs[0];
      const encodedDagRunId = encodeURIComponent(latestRun.dag_run_id);

      // 2. Determine tasks to process (target task + downstreams if clearDownstream)
      const tasksToProcess = new Set([taskId]);
      
      if (clearDownstream) {
        const tasksResponse = await apiClient.get(`/api/${apiVersion}/dags/${encodedDagId}/tasks`, {
          headers: { 'X-Composer-Environment': dag.environment.url }
        });
        const tasks = tasksResponse.data.tasks || [];
        const taskMap = {};
        tasks.forEach(t => taskMap[t.task_id] = t);
        
        const queue = [taskId];
        while (queue.length > 0) {
          const currentId = queue.shift();
          const currentTask = taskMap[currentId];
          if (currentTask && currentTask.downstream_task_ids) {
            currentTask.downstream_task_ids.forEach(downstreamId => {
              if (!tasksToProcess.has(downstreamId)) {
                tasksToProcess.add(downstreamId);
                queue.push(downstreamId);
              }
            });
          }
        }
      }

      // 3. For each task, find its instances in the DAG run and mark the relevant ones as 'failed'
      const tiResponse = await apiClient.get(`/api/${apiVersion}/dags/${encodedDagId}/dagRuns/${encodedDagRunId}/taskInstances?limit=1000`, {
        headers: { 'X-Composer-Environment': dag.environment.url }
      });
      const taskInstances = tiResponse.data.task_instances || [];
      
      const tasksActuallyFailed = new Set();
      const patchTasks = [];

      for (const tId of tasksToProcess) {
        const instances = taskInstances.filter(ti => ti.task_id === tId);
        if (instances.length === 0) continue;
        
        const isMapped = instances.some(ti => ti.map_index !== undefined && ti.map_index >= 0);
        
        let targetInstances = [];
        if (isMapped) {
          targetInstances = instances.filter(ti => ti.map_index === mapIndex);
        } else {
          targetInstances = instances;
        }

        for (const ti of targetInstances) {
          const encodedTaskId = encodeURIComponent(ti.task_id);
          let patchUrl = `/api/${apiVersion}/dags/${encodedDagId}/dagRuns/${encodedDagRunId}/taskInstances/${encodedTaskId}`;
          
          if (apiVersion !== 'v2' && ti.map_index !== undefined && ti.map_index >= 0) {
            patchUrl += `/${ti.map_index}`;
          }
          
          patchTasks.push({ url: patchUrl, tId: tId });
        }
      }

      for (const pt of patchTasks) {
        try {
          await apiClient.patch(pt.url, { new_state: 'failed' }, { 
            headers: { 'X-Composer-Environment': dag.environment.url },
            timeout: 10000
          });
        } catch (e) {
          if (e.code === 'ECONNABORTED' || (e.response && e.response.status === 500 && e.response.data && e.response.data.detail && String(e.response.data.detail).includes("ReadTimeout"))) {
            console.warn("Patch request timed out. Assuming it is processing in the background.", e);
          } else {
            throw e;
          }
        }
        tasksActuallyFailed.add(pt.tId);
      }

      // 4. Clear ONLY the failed instances of the tasks we processed
      if (tasksActuallyFailed.size > 0) {
        const latestRunDate = latestRun.logical_date || latestRun.execution_date;
        const clearUrl = `/api/${apiVersion}/dags/${encodedDagId}/clearTaskInstances`;
        const clearPayload = {
          dry_run: false,
          task_ids: Array.from(tasksActuallyFailed),
          only_failed: true,
          include_downstream: false,
          start_date: latestRunDate,
          end_date: latestRunDate
        };
        try {
          await apiClient.post(clearUrl, clearPayload, { 
            headers: { 'X-Composer-Environment': dag.environment.url },
            timeout: 10000
          });
        } catch (e) {
          if (e.code === 'ECONNABORTED' || (e.response && e.response.status === 500 && e.response.data && e.response.data.detail && String(e.response.data.detail).includes("ReadTimeout"))) {
            console.warn("Clear task request timed out. Assuming it is processing in the background.", e);
          } else {
            throw e;
          }
        }
      }
      
      fetchDags();
      setResponse({
        data: { message: `Successfully executed clear mapped task request for DAG ${dag.dag_id}, Task ${taskId} (Map Index: ${mapIndex}). (Note: Some operations may take time to process in the background)` },
        status: 200,
        statusText: "OK"
      });
      setShowModal(true);
    } catch (err) {
      let errorDetails = err.message;
      if (err.response && err.response.data) {
        errorDetails = typeof err.response.data === 'string' ? err.response.data : JSON.stringify(err.response.data);
      }
      setError(`Error: ${errorDetails}`);
      setShowModal(true);
    } finally {
      setIsBulkUpdating(false);
    }
  };

  // Compute displayed items on every render
  const unassociatedErrors = importErrors.filter(error => {
    return !dags.some(dag => {
      const envMatches = (!dag.environment || !error.environment || (dag.environment.name === error.environment.name && dag.environment.project === error.environment.project));
      const fileMatches = (error.filename && dag.fileloc && error.filename === dag.fileloc) || (dag.file_token && error.filename && error.filename.endsWith(dag.file_token)) || (dag.fileloc && error.filename && dag.fileloc.includes(error.filename));
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
      <th className="resizable-th" style={{ width: '150px' }}>
        <div className="d-flex align-items-center justify-content-between p-2">
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
        const fileMatches = (error.filename && item.fileloc && error.filename === item.fileloc) || (item.file_token && error.filename && error.filename.endsWith(item.file_token)) || (item.fileloc && error.filename && item.fileloc.includes(error.filename));
        return envMatches && fileMatches;
      });
    });
  }

  if (showRunningDagsOnly) {
    displayedItems = displayedItems.filter(item => item.last_runs && item.last_runs.some(run => run.state === 'running'));
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

    const apiVersion = currentEnvironment?.imageVersion?.includes('-airflow-3') ? 'v2' : 'v1';
    let finalPath = endpoint.path.replace('/api/v1/', `/api/${apiVersion}/`);
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
        let parsedBody = JSON.parse(body);
        if (endpoint.id === 'trigger-dag-run' && apiVersion === 'v2') {
          if (!parsedBody.logical_date) {
            parsedBody.logical_date = new Date().toISOString();
          }
        }
        config.data = parsedBody;
      } else if (endpoint.id === 'trigger-dag-run' && apiVersion === 'v2') {
        config.data = { logical_date: new Date().toISOString() };
      }

      const result = await apiClient(config);
      setTriggeredEnvironment(currentEnvironment);
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
      setShowModal(true);
    } catch (err) {
      setTriggeredEnvironment(null);
      setError(err.response || err.message);
      setResponse(null);
      setShowModal(true);
    }
  };

  if (!endpoint) {
    return <div>Select an endpoint from the sidebar.</div>;
  }

  const apiVersion = currentEnvironment?.imageVersion?.includes('-airflow-3') ? 'v2' : 'v1';
  const displayPath = endpoint.path.replace('/api/v1/', `/api/${apiVersion}/`);

  const getBadgeVariant = (method) => {
    switch (method.toUpperCase()) {
      case 'GET': return 'success';
      case 'POST': return 'primary';
      case 'PATCH': return 'warning';
      case 'DELETE': return 'danger';
      default: return 'secondary';
    }
  };

  // Helper components moved outside the EndpointView function body to prevent remounting on render

  if (endpoint.id === 'get-dags') {
    return (
      <Card>
        <Card.Body>


          <Button variant="primary" onClick={fetchDags} className="mb-3">Refresh DAGs</Button>
          <div className="mb-3">
            <Button variant="warning" onClick={() => handleToggleAllDags(true)} className="me-2" disabled={isBulkUpdating}>Pause All DAGs</Button>
            <Button variant="success" onClick={() => handleToggleAllDags(false)} className="me-2" disabled={isBulkUpdating}>Unpause All DAGs</Button>
            <Button variant="danger" onClick={handleFailRunningDags} className="me-2" disabled={isBulkUpdating}>Fail Running DAGs</Button>
            <Button variant="secondary" onClick={handleClearExistingTasks} disabled={isBulkUpdating}>Clear Existing Tasks</Button>
          </div>
          <div className="mb-3 d-flex align-items-center">
            <Button variant="warning" onClick={handlePauseSelectedDags} className="me-2" disabled={selectedDags.length === 0 || isBulkUpdating}>Pause Selected</Button>
            <Button variant="success" onClick={handleUnpauseSelectedDags} className="me-2" disabled={selectedDags.length === 0 || isBulkUpdating}>Unpause Selected</Button>
            <Button variant="danger" onClick={handleFailRunningTasks} className="me-2" disabled={selectedDags.length === 0 || isBulkUpdating}>Fail Running Tasks</Button>
            <Button variant="secondary" onClick={handleClearExistingTasksSelected} className="me-2" disabled={selectedDags.length === 0 || isBulkUpdating}>Clear Existing Tasks Selected</Button>
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
                  variant={showRunningDagsOnly ? "primary" : "outline-primary"}
                  onClick={() => setShowRunningDagsOnly(!showRunningDagsOnly)}
                  title={showRunningDagsOnly ? "Show All DAGs" : "Filter to running DAGs"}
                  className="text-nowrap"
                >
                  {showRunningDagsOnly ? "Show All DAGs" : "Show Running DAGs Only"}
                </Button>
                <Dropdown className="d-inline-block">
                  <Dropdown.Toggle variant="outline-primary" id="dropdown-columns" className="text-nowrap">
                    ⚙️ Columns
                  </Dropdown.Toggle>
                  <Dropdown.Menu className="p-3" style={{ minWidth: '220px', zIndex: 1050 }}>
                    <h6 className="dropdown-header px-0">Show/Hide Columns</h6>
                    {columnsList.map(col => (
                      <Form.Check 
                        key={col.key}
                        type="checkbox"
                        id={`col-toggle-${col.key}`}
                        label={col.label}
                        checked={visibleColumns[col.key]}
                        onChange={() => toggleColumnVisibility(col.key)}
                        className="mb-2"
                      />
                    ))}
                  </Dropdown.Menu>
                </Dropdown>
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
            <div className="table-responsive dags-table-container">
              <Table striped bordered hover key={filter} className="table-resizable">
                <thead>
                  <tr>
                    <th className="resizable-th sticky-col-1" style={{ width: '40px' }}><div className="p-2"><Form.Check type="checkbox" onChange={handleSelectAllDags} /></div></th>
                    <th className="resizable-th sticky-col-2" style={{ width: '150px' }}><div className="p-2">Actions</div></th>
                    <th className="resizable-th sticky-col-3" style={{ width: '300px' }}><div className="p-2">DAG ID</div></th>
                    <th className="resizable-th" style={{ width: '120px' }}><div className="p-2">Recent Runs</div></th>
                    {visibleColumns.project && renderHeaderWithFilter('Project', 'project')}
                    {visibleColumns.environment && renderHeaderWithFilter('Environment', 'environment')}
                    {visibleColumns.is_paused && renderHeaderWithFilter('Paused', 'is_paused')}
                    {visibleColumns.schedule_interval && renderHeaderWithFilter('Schedule', 'schedule_interval')}
                    {visibleColumns.owners && renderHeaderWithFilter('Owners', 'owners')}
                    {visibleColumns.tags && renderHeaderWithFilter('Tags', 'tags')}
                    {visibleColumns.next_dagrun && <th className="resizable-th" style={{ width: '200px' }}><div className="p-2">Next DAG Run</div></th>}
                    {visibleColumns.last_parsed_time && <th className="resizable-th" style={{ width: '200px' }}><div className="p-2">Last Parsed</div></th>}
                    {visibleColumns.fileloc && <th className="resizable-th" style={{ width: '250px' }}><div className="p-2">DAG File</div></th>}
                  </tr>
                </thead>
                <tbody>
                  {displayedItems.map(item => {
                      if (item.is_broken) {
                        return (
                          <tr key={`error-${item.environment ? `${item.environment.project}-${item.environment.name}` : 'unknown'}-${item.fileloc}-${item.error_details.timestamp}`} className="table-danger">
                            <td className="sticky-col-1"><Form.Check type="checkbox" disabled /></td>
                            <td className="sticky-col-2">
                              <div className="d-grid gap-2">
                                <Button variant="danger" size="sm" onClick={() => alert(item.error_details.stack_trace)}>View Trace</Button>
                                <Link to={`/edit-dag/${encodeURIComponent(item.dag_id)}/${item.environment ? item.environment.project : 'unknown'}/${item.environment ? item.environment.name : 'unknown'}?filename=${encodeURIComponent(item.fileloc)}&line=${extractLineNumber(item.error_details.stack_trace, item.fileloc)}`} className="btn btn-info btn-sm">Edit</Link>
                              </div>
                            </td>
                            <td className="sticky-col-3">
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
                            <td><span className="text-muted small">N/A</span></td>
                            {visibleColumns.project && <td>{item.environment ? item.environment.project : 'Unknown'}</td>}
                            {visibleColumns.environment && <td>{item.environment ? item.environment.name : 'Unknown'}</td>}
                            {visibleColumns.is_paused && <td>N/A</td>}
                            {visibleColumns.schedule_interval && <td>N/A</td>}
                            {visibleColumns.owners && <td>Error</td>}
                            {visibleColumns.tags && <td></td>}
                            {visibleColumns.next_dagrun && <td>N/A</td>}
                            {visibleColumns.last_parsed_time && <td>{item.last_parsed_time}</td>}
                            {visibleColumns.fileloc && <td>{item.fileloc}</td>}
                          </tr>
                        );
                      }

                      const dag = item;
                      const cloudStorageUrl = `https://console.cloud.google.com/storage/browser/_details/${dag.bucket}/dags/${dag.dag_id}.py`;
                      const associatedError = importErrors.find(error => {
                        const envMatches = (!dag.environment || !error.environment || (dag.environment.name === error.environment.name && dag.environment.project === error.environment.project));
                        const fileMatches = (error.filename && dag.fileloc && error.filename === dag.fileloc) || (dag.file_token && error.filename && error.filename.endsWith(dag.file_token)) || (dag.fileloc && error.filename && dag.fileloc.includes(error.filename));
                        return envMatches && fileMatches;
                      });

                      return (
                        <tr key={`${dag.environment.project}-${dag.environment.name}-${dag.dag_id}`}>
                          <td className="sticky-col-1"><Form.Check type="checkbox" checked={selectedDags.some(d => d.dag_id === dag.dag_id && d.env === dag.environment.name)} onChange={(e) => handleSelectDag(e, dag.dag_id, dag.environment.name)} /></td>
                          <td className="sticky-col-2">
                            <div className="d-grid gap-2">
                              {!associatedError && (
                                <>
                                  {!dag.is_paused ? (
                                    <Button
                                      variant="warning"
                                      size="sm"
                                      onClick={async () => {
                                        const success = await toggleDagPaused(dag.dag_id, true, dag.environment);
                                        if (success) {
                                          setDags(prevDags => prevDags.map(d => 
                                            d.dag_id === dag.dag_id && d.environment.name === dag.environment.name 
                                              ? { ...d, is_paused: true } 
                                              : d
                                          ));
                                        }
                                      }}
                                    >
                                      Pause
                                    </Button>
                                  ) : (
                                    <Button
                                      variant="success"
                                      size="sm"
                                      onClick={async () => {
                                        const success = await toggleDagPaused(dag.dag_id, false, dag.environment);
                                        if (success) {
                                          setDags(prevDags => prevDags.map(d => 
                                            d.dag_id === dag.dag_id && d.environment.name === dag.environment.name 
                                              ? { ...d, is_paused: false } 
                                              : d
                                          ));
                                        }
                                      }}
                                    >
                                      Unpause
                                    </Button>
                                  )}
                                  <Button
                                    variant="primary"
                                    size="sm"
                                    onClick={() => handleTriggerClick(dag)}
                                    title="Trigger DAG"
                                  >
                                    Trigger
                                  </Button>
                                  <Button
                                    variant="secondary"
                                    size="sm"
                                    onClick={() => handleReparseClick(dag)}
                                    title="Reparse DAG"
                                  >
                                    Reparse
                                  </Button>
                                    <Button
                                      variant="danger"
                                      size="sm"
                                      onClick={() => handleFailDagRunningTasks(dag)}
                                      title="Fail Running Tasks"
                                      disabled={isBulkUpdating}
                                    >
                                      Fail Tasks
                                    </Button>
                                    <Button
                                      variant="secondary"
                                      size="sm"
                                      onClick={() => handleClearDagTasks(dag)}
                                      title="Clear Tasks"
                                      disabled={isBulkUpdating}
                                    >
                                      Clear Tasks
                                    </Button>
                                    <Button
                                      variant="outline-secondary"
                                      size="sm"
                                      onClick={() => {
                                        setClearingMappedDag(dag);
                                        setShowClearMappedModal(true);
                                      }}
                                      title="Clear Mapped Task"
                                      disabled={isBulkUpdating}
                                    >
                                      Clear Mapped Task
                                    </Button>
                                </>
                              )}
                              <Link to={`/edit-dag/${dag.dag_id}/${dag.environment.project}/${dag.environment.name}?filename=${encodeURIComponent(dag.fileloc)}${associatedError ? `&line=${extractLineNumber(associatedError.stack_trace, dag.fileloc)}` : ''}`} className="btn btn-info btn-sm">Edit</Link>
                            </div>
                          </td>
                          <td className="sticky-col-3">
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
                          <td>
                            <div className="d-flex gap-1 align-items-center">
                              {dag.last_runs && dag.last_runs.length > 0 ? (
                                dag.last_runs.map((run, idx) => {
                                  let color = '#6c757d'; // default grey
                                  if (run.state === 'success') color = '#198754'; // bootstrap success green
                                  else if (run.state === 'failed') color = '#dc3545'; // bootstrap danger red
                                  else if (run.state === 'running') color = '#0d6efd'; // bootstrap primary blue
                                  else if (run.state === 'queued') color = '#ffc107'; // bootstrap warning yellow

                                  const envUrl = dag.environment.url.replace(/\/$/, "");
                                  const isAirflow3 = dag.environment.imageVersion && dag.environment.imageVersion.includes('-airflow-3');
                                  const runUrl = isAirflow3 
                                    ? `${envUrl}/dags/${dag.dag_id}/runs/${encodeURIComponent(run.dag_run_id)}`
                                    : `${envUrl}/dags/${dag.dag_id}/grid?dag_run_id=${encodeURIComponent(run.dag_run_id)}`;

                                  return (
                                    <a
                                      key={run.dag_run_id || idx}
                                      href={runUrl}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="d-inline-block rounded-circle"
                                      style={{
                                        width: '12px',
                                        height: '12px',
                                        backgroundColor: color,
                                        cursor: 'pointer',
                                        boxShadow: run.state === 'running' ? '0 0 6px #0d6efd' : 'none',
                                        transition: 'transform 0.1s ease-in-out'
                                      }}
                                      title={`${run.dag_run_id} (${run.state})`}
                                      onMouseEnter={(e) => e.target.style.transform = 'scale(1.3)'}
                                      onMouseLeave={(e) => e.target.style.transform = 'scale(1.0)'}
                                    />
                                  );
                                })
                              ) : (
                                <span className="text-muted small" style={{ fontSize: '11px' }}>No runs</span>
                              )}
                            </div>
                          </td>
                          {visibleColumns.project && <td>{dag.environment.project}</td>}
                          {visibleColumns.environment && <td>{dag.environment.name}</td>}
                          {visibleColumns.is_paused && <td>{dag.is_paused.toString()}</td>}
                          {visibleColumns.schedule_interval && <td>{dag.schedule_interval?.value}</td>}
                          {visibleColumns.owners && <td>{dag.owners?.join(', ')}</td>}
                          {visibleColumns.tags && <td>{dag.tags?.map(tag => typeof tag === 'object' ? tag.name : tag).join(', ')}</td>}
                          {visibleColumns.next_dagrun && <td>{dag.next_dagrun}</td>}
                          {visibleColumns.last_parsed_time && <td>{dag.last_parsed_time}</td>}
                          {visibleColumns.fileloc && <td><a href={cloudStorageUrl} target="_blank" rel="noopener noreferrer">{`${dag.dag_id}.py`}</a></td>}
                        </tr>
                      );
                    })}
                </tbody>
              </Table>
            </div>
            </>
          )}
        </Card.Body>
        <ResponseModal
          show={showModal}
          onHide={handleCloseModal}
          response={response}
          error={error}
          endpoint={endpoint}
          environment={triggeredEnvironment || currentEnvironment}
        />
        <TriggerModal
          show={showTriggerModal}
          onHide={() => { setShowTriggerModal(false); setTriggeringDag(null); }}
          triggeringDag={triggeringDag}
          paramValues={paramValues}
          setParamValues={setParamValues}
          onTrigger={triggerDag}
        />
        <ClearMappedTaskModal
          show={showClearMappedModal}
          onHide={() => { setShowClearMappedModal(false); setClearingMappedDag(null); }}
          dag={clearingMappedDag}
          onClear={handleClearMappedSubmit}
        />
      </Card>
    );
  }

  return (
    <Card>
      <Card.Header>
        <h4>
          <Badge bg={getBadgeVariant(endpoint.method)} className="me-2">{endpoint.method}</Badge>
          {displayPath}
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

      <ResponseModal
        show={showModal}
        onHide={handleCloseModal}
        response={response}
        error={error}
        endpoint={endpoint}
        environment={triggeredEnvironment || currentEnvironment}
      />
    </Card>
  );
}

const ResponseModal = ({ show, onHide, response, error, endpoint, environment }) => {
  const dagRunId = response?.data?.dag_run_id;
  const dagId = response?.data?.dag_id;
  const envUrl = environment?.url?.replace(/\/$/, "");
  const isAirflow3 = environment?.imageVersion?.includes('-airflow-3');

  const showLink = dagRunId && dagId && envUrl && envUrl !== 'all';
  const dagRunUrl = showLink 
    ? (isAirflow3 
        ? `${envUrl}/dags/${dagId}/runs/${encodeURIComponent(dagRunId)}`
        : `${envUrl}/dags/${dagId}/grid?dag_run_id=${encodeURIComponent(dagRunId)}`)
    : null;

  return (
    <Modal show={show} onHide={onHide} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>{error ? 'Error' : 'Response'}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {response && (
          <>
            <Alert variant="success">
              <div>
                <strong>Status: {response.status} {response.statusText}</strong>
              </div>
              {dagRunUrl && (
                <div className="mt-2">
                  <a href={dagRunUrl} target="_blank" rel="noopener noreferrer" className="btn btn-primary btn-sm">
                    View Triggered DAG Run in Airflow UI
                  </a>
                </div>
              )}
            </Alert>
            {endpoint && endpoint.id === 'get-dag-runs' && response.data.dag_runs ? (
              <Table responsive striped bordered hover className="table-resizable" size="sm">
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
              <pre style={{ maxHeight: '400px', overflow: 'auto' }}>
                {JSON.stringify(response.data, null, 2)}
              </pre>
            )}
          </>
        )}
        {error && (
          <>
            <Alert variant="danger">
              <strong>Error: {error.status ? `${error.status} ${error.statusText}` : error}</strong>
            </Alert>
            {error.data && (
              <pre style={{ maxHeight: '400px', overflow: 'auto' }}>
                {JSON.stringify(error.data, null, 2)}
              </pre>
            )}
          </>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>Close</Button>
      </Modal.Footer>
    </Modal>
  );
};

const TriggerModal = ({ show, onHide, triggeringDag, paramValues, setParamValues, onTrigger }) => {
  if (!triggeringDag) return null;

  const handleParamValChange = (e) => {
    setParamValues(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleModalTrigger = async () => {
    onHide();
    await onTrigger(triggeringDag.dag_id, triggeringDag.environment, paramValues);
  };

  return (
    <Modal show={show} onHide={onHide}>
      <Modal.Header closeButton>
        <Modal.Title>Trigger DAG: {triggeringDag.dag_id}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Form>
          {Object.keys(triggeringDag.params).map(key => {
            const param = triggeringDag.params[key];
            const val = (param && typeof param === 'object' && 'value' in param) ? param.value : param;
            const description = (param && typeof param === 'object') ? param.description : null;
            const schemaType = (param && typeof param === 'object' && param.schema) ? param.schema.type : null;
            const isBoolean = schemaType === 'boolean' || typeof val === 'boolean';
            const isNumber = schemaType === 'integer' || schemaType === 'number' || (Array.isArray(schemaType) && (schemaType.includes('integer') || schemaType.includes('number'))) || typeof val === 'number';

            return (
              <Form.Group className="mb-3" key={key}>
                {isBoolean ? (
                   <Form.Check
                     type="checkbox"
                     label={key}
                     name={key}
                     checked={!!paramValues[key]}
                     onChange={(e) => setParamValues(prev => ({ ...prev, [key]: e.target.checked }))}
                   />
                ) : (
                  <>
                    <Form.Label>{key}</Form.Label>
                    <Form.Control
                      type={isNumber ? "number" : "text"}
                      name={key}
                      value={paramValues[key] === undefined || paramValues[key] === null ? '' : paramValues[key]}
                      onChange={(e) => {
                        let newValue = e.target.value;
                        if (isNumber && newValue !== '') {
                          newValue = Number(newValue);
                        }
                        setParamValues(prev => ({ ...prev, [key]: newValue }));
                      }}
                    />
                  </>
                )}
                {description && <Form.Text className="text-muted d-block">{description}</Form.Text>}
              </Form.Group>
            );
          })}
        </Form>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>Cancel</Button>
        <Button variant="primary" onClick={handleModalTrigger}>Trigger</Button>
      </Modal.Footer>
    </Modal>
  );
};

const ClearMappedTaskModal = ({ show, onHide, dag, onClear }) => {
  const [mapIndex, setMapIndex] = useState('');
  const [taskId, setTaskId] = useState('');
  const [tasks, setTasks] = useState([]);
  const [clearDownstream, setClearDownstream] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (show && dag) {
      setMapIndex('');
      setTaskId('');
      setClearDownstream(false);
      setTasks([]);
      setIsLoading(true);

      // Use dynamic import or standard apiClient if it's already in scope (it is)
      const apiVersion = dag.environment.imageVersion && dag.environment.imageVersion.includes('-airflow-3') ? 'v2' : 'v1';
      const encodedDagId = encodeURIComponent(dag.dag_id);
      
      apiClient.get(`/api/${apiVersion}/dags/${encodedDagId}/tasks`, {
        headers: { 'X-Composer-Environment': dag.environment.url }
      }).then(response => {
        if (response.data && response.data.tasks) {
          setTasks(response.data.tasks);
          if (response.data.tasks.length > 0) {
            setTaskId(response.data.tasks[0].task_id);
          }
        }
      }).catch(err => {
        console.error("Failed to fetch tasks", err);
      }).finally(() => {
        setIsLoading(false);
      });
    }
  }, [show, dag]);

  const handleClear = () => {
    onHide();
    onClear(dag, taskId, parseInt(mapIndex, 10), clearDownstream);
  };

  return (
    <Modal show={show} onHide={onHide}>
      <Modal.Header closeButton>
        <Modal.Title>Clear Mapped Task: {dag?.dag_id}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {isLoading ? (
          <div className="d-flex justify-content-center">
            <Spinner animation="border" size="sm" /> <span className="ms-2">Loading tasks...</span>
          </div>
        ) : (
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Task ID</Form.Label>
              <Form.Select 
                value={taskId} 
                onChange={(e) => setTaskId(e.target.value)}
                disabled={tasks.length === 0}
              >
                <option value="">Select a task...</option>
                {tasks.map(t => (
                  <option key={t.task_id} value={t.task_id}>{t.task_id}</option>
                ))}
              </Form.Select>
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Mapped Index</Form.Label>
              <Form.Control
                type="number"
                value={mapIndex}
                onChange={(e) => setMapIndex(e.target.value)}
                placeholder="Enter mapped index (e.g. 0)"
              />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Check
                type="checkbox"
                id="clear-downstream-check"
                label="Clear downstream dependent tasks with the same mapped index"
                checked={clearDownstream}
                onChange={(e) => setClearDownstream(e.target.checked)}
              />
            </Form.Group>
          </Form>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>Cancel</Button>
        <Button variant="primary" onClick={handleClear} disabled={mapIndex === '' || taskId === ''}>Clear</Button>
      </Modal.Footer>
    </Modal>
  );
};

export default EndpointView;