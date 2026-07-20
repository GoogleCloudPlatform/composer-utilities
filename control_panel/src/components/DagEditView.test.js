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
import { render, screen, waitFor } from '@testing-library/react';
import DagEditView from './DagEditView';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '../context/ThemeContext';
import apiClient from '../api/axios';

jest.mock('../api/axios');

describe('DagEditView Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders DagEditView and fetches environments', async () => {
    apiClient.get.mockResolvedValue({ data: [] });

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/edit-dag/test-dag/test-project/test-env']}>
          <Routes>
            <Route path="/edit-dag/:dagId/:project/:env" element={<DagEditView />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    expect(screen.getByText(/Editing DAG:/i)).toBeInTheDocument();
    
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/api/environments');
    });
  });
});
