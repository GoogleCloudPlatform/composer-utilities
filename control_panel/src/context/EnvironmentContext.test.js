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
