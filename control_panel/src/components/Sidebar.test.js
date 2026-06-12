import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import Sidebar from './Sidebar';
import { EnvironmentProvider } from '../context/EnvironmentContext';
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

    render(
      <BrowserRouter>
        <EnvironmentProvider>
          <Sidebar />
        </EnvironmentProvider>
      </BrowserRouter>
    );

    expect(screen.getByText('Airflow API')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/api/environments');
    });
  });
});
