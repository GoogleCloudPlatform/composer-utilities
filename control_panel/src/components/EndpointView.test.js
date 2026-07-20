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
import EndpointView from './EndpointView';
import { EnvironmentProvider } from '../context/EnvironmentContext';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import apiClient from '../api/axios';

jest.mock('../api/axios');

describe('EndpointView Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
});
