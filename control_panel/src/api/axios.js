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


import axios from 'axios';

const apiClient = axios.create({
  // npm run build command automatically sets process.env.NODE_ENV to "production".
  // npm start sets it to "development". 
  // This is a standard convention managed by the react-scripts package.
  baseURL: process.env.NODE_ENV === 'production'
    ? window.location.origin
    : 'http://localhost:3001',
});

const getEnvironment = () => {
  try {
    const item = window.localStorage.getItem('currentEnvironment');
    return item ? JSON.parse(item) : null;
  } catch (error) {
    console.error(error);
    return null;
  }
};

apiClient.interceptors.request.use(
  (config) => {
    const environment = getEnvironment();
    if (environment && environment.url && environment.url !== 'all') {
      config.headers['X-Composer-Environment'] = environment.url;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default apiClient;
