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
import { Nav, Dropdown } from 'react-bootstrap';
import { LinkContainer } from 'react-router-bootstrap';
import { useEnvironment } from '../context/EnvironmentContext';
import apiClient from '../api/axios';

function Sidebar() {
  const { currentEnvironment, setCurrentEnvironment } = useEnvironment();
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
    <div className="sticky-top">
      <h4 className="mb-3">Airflow API</h4>

      <Dropdown className="mb-3">
        <Dropdown.Toggle variant="success" id="dropdown-basic">
          {currentEnvironment ? (currentEnvironment.project ? `${currentEnvironment.name} (${currentEnvironment.project})` : currentEnvironment.name) : 'Select Environment'}
        </Dropdown.Toggle>

        <Dropdown.Menu>
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

      <Nav className="flex-column">
        <LinkContainer to="/endpoint/get-dags">
          <Nav.Link className="d-flex justify-content-between align-items-center mb-2 p-2 border rounded border-success text-success fw-bold bg-light">
            <span>All DAGs</span>
          </Nav.Link>
        </LinkContainer>
      </Nav>
    </div>
  );
}

export default Sidebar;
