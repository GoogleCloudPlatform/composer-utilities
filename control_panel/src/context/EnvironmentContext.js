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


import React, { createContext, useState, useContext, useCallback } from 'react';

const EnvironmentContext = createContext();

export const useEnvironment = () => useContext(EnvironmentContext);

export const EnvironmentProvider = ({ children }) => {
  const [currentEnvironment, setCurrentEnvironment] = useState(() => {
    try {
      const item = window.localStorage.getItem('currentEnvironment');
      return item ? JSON.parse(item) : null;
    } catch (error) {
      console.error(error);
      return null;
    }
  });

  const setEnvironment = useCallback((environment) => {
    try {
      setCurrentEnvironment(environment);
      window.localStorage.setItem('currentEnvironment', JSON.stringify(environment));
    } catch (error) {
      console.error(error);
    }
  }, []);

  return (
    <EnvironmentContext.Provider value={{ currentEnvironment, setCurrentEnvironment: setEnvironment }}>
      {children}
    </EnvironmentContext.Provider>
  );
};
