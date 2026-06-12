import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import DagEditView from './DagEditView';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import apiClient from '../api/axios';

jest.mock('../api/axios');

describe('DagEditView Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders DagEditView and fetches environments', async () => {
    apiClient.get.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter initialEntries={['/edit-dag/test-dag/test-project/test-env']}>
        <Routes>
          <Route path="/edit-dag/:dagId/:project/:env" element={<DagEditView />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText(/Editing DAG:/i)).toBeInTheDocument();
    
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/api/environments');
    });
  });
});
