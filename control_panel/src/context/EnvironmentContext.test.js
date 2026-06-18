import React from 'react';
import { render, screen } from '@testing-library/react';
import { EnvironmentProvider, useEnvironment } from './EnvironmentContext';

const TestComponent = () => {
  const { currentEnvironment } = useEnvironment();
  return <div>{currentEnvironment ? currentEnvironment.name : 'No Environment'}</div>;
};

describe('EnvironmentContext', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  test('provides default environment from localStorage', () => {
    window.localStorage.setItem('currentEnvironment', JSON.stringify({ name: 'TestEnv' }));
    
    render(
      <EnvironmentProvider>
        <TestComponent />
      </EnvironmentProvider>
    );

    expect(screen.getByText('TestEnv')).toBeInTheDocument();
  });

  test('provides no environment when localStorage is empty', () => {
    render(
      <EnvironmentProvider>
        <TestComponent />
      </EnvironmentProvider>
    );

    expect(screen.getByText('No Environment')).toBeInTheDocument();
  });
});
