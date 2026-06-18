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

export const apiSections = [
  {
    title: 'DAGs',
    endpoints: [
      {
        id: 'get-dags',
        method: 'GET',
        path: '/api/v1/dags',
        description: 'Get all DAGs.',
        parameters: {
          query: [
            { name: 'limit', type: 'integer', description: 'The numbers of items to return.' },
            { name: 'offset', type: 'integer', description: 'The number of items to skip.' },
            { name: 'tags', type: 'string', description: 'Filter by tags.' },
          ],
          path: [],
        },
        body: null,
      },
      {
        id: 'get-dag-details',
        method: 'GET',
        path: '/api/v1/dags/{dag_id}/details',
        description: 'Get details of a DAG.',
        parameters: {
          query: [],
          path: [{ name: 'dag_id', type: 'string', description: 'The DAG ID.' }],
        },
        body: null,
      },
      {
        id: 'patch-dag',
        method: 'PATCH',
        path: '/api/v1/dags/{dag_id}',
        description: 'Update a DAG.',
        parameters: {
            query: [],
            path: [{ name: 'dag_id', type: 'string', description: 'The DAG ID.' }],
        },
        body: { type: 'application/json', schema: { is_paused: 'boolean' } }
      },
      {
        id: 'get-dag-tasks',
        method: 'GET',
        path: '/api/v1/dags/{dag_id}/tasks',
        description: 'Get tasks for a DAG.',
        parameters: {
            query: [],
            path: [{ name: 'dag_id', type: 'string', description: 'The DAG ID.' }],
        },
        body: null
      },
      {
        id: 'get-dag-task-details',
        method: 'GET',
        path: '/api/v1/dags/{dag_id}/tasks/{task_id}',
        description: 'Get details of a DAG task.',
        parameters: {
            query: [],
            path: [
                { name: 'dag_id', type: 'string', description: 'The DAG ID.' },
                { name: 'task_id', type: 'string', description: 'The Task ID.' },
            ],
        },
        body: null
      },
      {
        id: 'trigger-dag-run',
        method: 'POST',
        path: '/api/v1/dags/{dag_id}/dagRuns',
        description: 'Trigger a new DAG run.',
        parameters: {
          query: [],
          path: [{ name: 'dag_id', type: 'string', description: 'The DAG ID.' }],
        },
        body: { type: 'application/json', schema: {} }
      },
    ],
  }
];