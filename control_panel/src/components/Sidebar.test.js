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
import { render, screen, waitFor, act } from '@testing-library/react';
import Sidebar from './Sidebar';
import { EnvironmentProvider } from '../context/EnvironmentContext';
import { ThemeProvider } from '../context/ThemeContext';
import { BrowserRouter } from 'react-router-dom';
import apiClient from '../api/axios';

jest.mock('../api/axios');

describe('Sidebar Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders Sidebar and fetches environments', async () => {
    apiClient.get.mockResolvedValue({
      data: [
        { name: 'env1', project: 'proj1', url: 'url1' },
        { name: 'env2', project: 'proj2', url: 'url2' }
      ]
    });

    await act(async () => {
      render(
        <BrowserRouter>
          <ThemeProvider>
            <EnvironmentProvider>
              <Sidebar />
            </EnvironmentProvider>
          </ThemeProvider>
        </BrowserRouter>
      );
    });

    expect(screen.getByText('Control Panel')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/api/environments');
    });
  });
});
