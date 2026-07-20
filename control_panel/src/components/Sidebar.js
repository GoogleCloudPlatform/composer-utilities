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

import React, { useState, useEffect } from 'react';
import { Dropdown, Button } from 'react-bootstrap';
import { useEnvironment } from '../context/EnvironmentContext';
import { useTheme } from '../context/ThemeContext';
import apiClient from '../api/axios';

function Sidebar() {
  const { currentEnvironment, setCurrentEnvironment } = useEnvironment();
  const { theme, toggleTheme } = useTheme();
  const [environments, setEnvironments] = useState([]);

  useEffect(() => {
    apiClient.get('/api/environments')
      .then(response => {
        setEnvironments(response.data);
        if (!currentEnvironment) {
          setCurrentEnvironment({ name: 'All Environments', url: 'all' });
        }
      })
      .catch(error => console.error('Error fetching environments:', error));
  }, []);

  const getBadgeVariant = (method) => {
    switch (method.toUpperCase()) {
      case 'GET': return 'success';
      case 'POST': return 'primary';
      case 'PATCH': return 'warning';
      case 'DELETE': return 'danger';
      default: return 'secondary';
    }
  };

  return (
    <div className="h-100 d-flex flex-column justify-content-between">
      <div>
        <div className="mb-4 text-center">
          <img 
            src={process.env.PUBLIC_URL + '/logo512.png'} 
            alt="Composer Control Panel Logo" 
            className="img-fluid mb-3 shadow-sm rounded-circle" 
            style={{ maxWidth: '120px', border: '2px solid var(--accent-primary)', padding: '4px' }} 
          />
          <h4 className="fw-bold" style={{ color: 'var(--accent-primary)', fontFamily: 'var(--font-title)' }}>Control Panel</h4>
        </div>

        <Dropdown className="mb-3 w-100">
          <Dropdown.Toggle variant={theme === 'dark' ? 'outline-light' : 'outline-dark'} id="dropdown-basic" className="w-100 text-start d-flex justify-content-between align-items-center">
            <span>{currentEnvironment ? (currentEnvironment.project ? `${currentEnvironment.name} (${currentEnvironment.project})` : currentEnvironment.name) : 'Select Environment'}</span>
          </Dropdown.Toggle>

          <Dropdown.Menu className="w-100">
            <Dropdown.Item key="all" onClick={() => setCurrentEnvironment({ name: 'All Environments', url: 'all' })}>
              All Environments
            </Dropdown.Item>
            <Dropdown.Divider />
            {environments.map(env => (
              <Dropdown.Item key={`${env.project}-${env.location}-${env.name}`} onClick={() => setCurrentEnvironment(env)}>
                {env.name} ({env.project})
              </Dropdown.Item>
            ))}
          </Dropdown.Menu>
        </Dropdown>
      </div>

      <div className="pt-3 border-top border-secondary text-center">
        <Button variant={theme === 'dark' ? 'outline-light' : 'outline-dark'} size="sm" onClick={toggleTheme} className="w-100 d-flex align-items-center justify-content-center gap-2">
          {theme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode'}
        </Button>
      </div>
    </div>
  );
}

export default Sidebar;
