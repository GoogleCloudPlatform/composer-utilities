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
