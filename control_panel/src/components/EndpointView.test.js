/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import React from 'react';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import EndpointView from './EndpointView';
import { EnvironmentProvider } from '../context/EnvironmentContext';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import apiClient from '../api/axios';

jest.mock('../api/axios');

describe('EndpointView Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  test('renders EndpointView for get-dags', async () => {
    render(
      <MemoryRouter initialEntries={['/endpoint/get-dags']}>
        <Routes>
          <Route path="/endpoint/:endpointId" element={
            <EnvironmentProvider>
              <EndpointView />
            </EnvironmentProvider>
          } />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/get-dags|Select an endpoint/i)).toBeInTheDocument();
    });
  });

  test('renders Batch Operations by Pattern button and opens modal', async () => {
    const mockEnv = { name: 'test-env', url: 'https://test-airflow.com', project: 'test-proj' };
    localStorage.setItem('currentEnvironment', JSON.stringify(mockEnv));

    apiClient.get.mockImplementation((url) => {
      if (url.includes('/api/v1/dags')) {
        return Promise.resolve({
          data: {
            dags: [
              { dag_id: 'test_dag_1', is_paused: false, fileloc: '/dags/test_dag_1.py', owners: ['airflow'], tags: [] },
              { dag_id: 'prod_dag_2', is_paused: true, fileloc: '/dags/prod_dag_2.py', owners: ['airflow'], tags: [] }
            ]
          }
        });
      }
      if (url.includes('/details')) {
        return Promise.resolve({ data: { config: { dagGcsPrefix: 'gs://test-bucket/dags' } } });
      }
      if (url.includes('/importErrors')) {
        return Promise.resolve({ data: { import_errors: [] } });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <MemoryRouter initialEntries={['/endpoint/get-dags']}>
        <Routes>
          <Route path="/endpoint/:endpointId" element={
            <EnvironmentProvider>
              <EndpointView />
            </EnvironmentProvider>
          } />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Batch Operations by Pattern/i)).toBeInTheDocument();
    });

    // Open the modal
    const { fireEvent } = require('@testing-library/react');
    const batchButton = screen.getByText(/Batch Operations by Pattern/i);
    fireEvent.click(batchButton);

    await waitFor(() => {
      expect(screen.getByText(/About Airflow REST API Pattern Parameters/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Substring Pattern/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Prefix Pattern/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  test('previews matching DAGs via API in modal using prefix pattern', async () => {
    const mockEnv = { name: 'test-env', url: 'https://test-airflow.com', project: 'test-proj' };
    localStorage.setItem('currentEnvironment', JSON.stringify(mockEnv));

    apiClient.get.mockImplementation((url, config) => {
      if (url.includes('/api/v1/dags')) {
        // If query config contains dag_id_prefix_pattern
        if (config?.params?.dag_id_prefix_pattern === 'test_') {
          return Promise.resolve({
            data: {
              dags: [{ dag_id: 'test_dag_1', is_paused: false, fileloc: '/dags/test_dag_1.py', owners: ['airflow'], tags: [] }]
            }
          });
        }
        return Promise.resolve({
          data: {
            dags: [
              { dag_id: 'test_dag_1', is_paused: false, fileloc: '/dags/test_dag_1.py', owners: ['airflow'], tags: [] },
              { dag_id: 'prod_dag_2', is_paused: true, fileloc: '/dags/prod_dag_2.py', owners: ['airflow'], tags: [] }
            ]
          }
        });
      }
      if (url.includes('/details')) {
        return Promise.resolve({ data: { config: { dagGcsPrefix: 'gs://test-bucket/dags' } } });
      }
      if (url.includes('/importErrors')) {
        return Promise.resolve({ data: { import_errors: [] } });
      }
      return Promise.resolve({ data: {} });
    });

    const { fireEvent } = require('@testing-library/react');

    render(
      <MemoryRouter initialEntries={['/endpoint/get-dags']}>
        <Routes>
          <Route path="/endpoint/:endpointId" element={
            <EnvironmentProvider>
              <EndpointView />
            </EnvironmentProvider>
          } />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Batch Operations by Pattern/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Batch Operations by Pattern/i));

    await waitFor(() => {
      expect(screen.getByLabelText(/Pattern String Input/i)).toBeInTheDocument();
    });

    // Switch to prefix pattern
    const prefixRadio = screen.getByLabelText(/Prefix Pattern/i);
    fireEvent.click(prefixRadio);

    // Type pattern string
    const input = screen.getByLabelText(/Pattern String Input/i);
    fireEvent.change(input, { target: { value: 'test_' } });

    // Click Preview Matches button
    const previewBtn = screen.getByRole('button', { name: /Preview Matches via API/i });
    fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/dags'),
        expect.objectContaining({
          params: { dag_id_prefix_pattern: 'test_' }
        })
      );
      expect(screen.getByText(/Found 1 matching DAG\(s\)/i)).toBeInTheDocument();
    });
  });

  test('executes batch pause using prefix pattern', async () => {
    const mockEnv = { name: 'test-env', url: 'https://test-airflow.com', project: 'test-proj' };
    localStorage.setItem('currentEnvironment', JSON.stringify(mockEnv));

    apiClient.get.mockResolvedValue({
      data: { dags: [], config: { dagGcsPrefix: 'gs://test-bucket/dags' }, import_errors: [] }
    });
    apiClient.patch.mockResolvedValue({
      data: { dags: [{ dag_id: 'test_dag_1', is_paused: true }], total_entries: 1 }
    });

    const { fireEvent } = require('@testing-library/react');

    render(
      <MemoryRouter initialEntries={['/endpoint/get-dags']}>
        <Routes>
          <Route path="/endpoint/:endpointId" element={
            <EnvironmentProvider>
              <EndpointView />
            </EnvironmentProvider>
          } />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Batch Operations by Pattern/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Batch Operations by Pattern/i));

    await waitFor(() => {
      expect(screen.getByLabelText(/Pattern String Input/i)).toBeInTheDocument();
    });

    // Select prefix pattern
    fireEvent.click(screen.getByLabelText(/Prefix Pattern/i));

    // Input pattern value
    const input = screen.getByLabelText(/Pattern String Input/i);
    fireEvent.change(input, { target: { value: 'test_' } });

    // Execute
    const executeBtn = screen.getByText(/Execute Batch PAUSE/i);
    fireEvent.click(executeBtn);

    await waitFor(() => {
      expect(apiClient.patch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/dags?dag_id_prefix_pattern=test_&update_mask=is_paused'),
        { is_paused: true },
        expect.objectContaining({ headers: { 'X-Composer-Environment': mockEnv.url } })
      );
    });
  });

  test('filters DAG table via Airflow REST API pattern parameter', async () => {
    const mockEnv = { name: 'test-env', url: 'https://test-airflow.com', project: 'test-proj' };
    localStorage.setItem('currentEnvironment', JSON.stringify(mockEnv));

    apiClient.get.mockImplementation((url, config) => {
      if (url.includes('/api/v1/dags')) {
        if (config?.params?.dag_id_pattern === '%finance%') {
          return Promise.resolve({
            data: { dags: [{ dag_id: 'finance_report', is_paused: false, fileloc: '/dags/finance.py', owners: ['fin'], tags: [] }] }
          });
        }
        return Promise.resolve({
          data: { dags: [{ dag_id: 'finance_report', is_paused: false, fileloc: '/dags/finance.py', owners: ['fin'], tags: [] }] }
        });
      }
      if (url.includes('/details')) {
        return Promise.resolve({ data: { config: { dagGcsPrefix: 'gs://test-bucket/dags' } } });
      }
      if (url.includes('/importErrors')) {
        return Promise.resolve({ data: { import_errors: [] } });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <MemoryRouter initialEntries={['/endpoint/get-dags']}>
        <Routes>
          <Route path="/endpoint/:endpointId" element={
            <EnvironmentProvider>
              <EndpointView />
            </EnvironmentProvider>
          } />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Filter table or API pattern input/i)).toBeInTheDocument();
    });

    const apiInput = screen.getByLabelText(/Filter table or API pattern input/i);
    fireEvent.change(apiInput, { target: { value: '%finance%' } });

    const filterBtn = screen.getByText('Filter API');
    fireEvent.click(filterBtn);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/dags'),
        expect.objectContaining({
          params: { dag_id_pattern: '%finance%' }
        })
      );
      expect(screen.getByText(/Active Airflow REST API Filter/i)).toBeInTheDocument();
    });
  });
});
