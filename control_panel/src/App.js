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

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Container, Row, Col } from 'react-bootstrap';
import Sidebar from './components/Sidebar';
import EndpointView from './components/EndpointView';
import DagEditView from './components/DagEditView';
import './App.css';

function App() {
  const [sidebarWidth, setSidebarWidth] = useState(250);
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef(null);

  const startResizing = useCallback((mouseDownEvent) => {
    setIsResizing(true);
    document.body.classList.add('is-resizing');
  }, []);

  const stopResizing = useCallback(() => {
    setIsResizing(false);
    document.body.classList.remove('is-resizing');
  }, []);

  const resize = useCallback((mouseMoveEvent) => {
    if (isResizing && sidebarRef.current) {
      const newWidth = mouseMoveEvent.clientX - sidebarRef.current.getBoundingClientRect().left;
      // Define min and max widths
      if (newWidth > 200 && newWidth < Math.min(800, window.innerWidth * 0.5)) {
        setSidebarWidth(newWidth);
      }
    }
  }, [isResizing]);

  useEffect(() => {
    window.addEventListener('mousemove', resize);
    window.addEventListener('mouseup', stopResizing);
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [resize, stopResizing]);

  return (
    <Router>
      <Container fluid>
        <Row className="flex-nowrap">
          <Col xs="auto" className="bg-light vh-100 p-0 position-relative" style={{ width: sidebarWidth }} ref={sidebarRef}>
            <div className="p-3 h-100 overflow-auto" style={{ width: '100%' }}>
              <Sidebar />
            </div>
            <div className="resize-handle" onMouseDown={startResizing} />
          </Col>
          <Col className="p-3 overflow-auto">
            <Routes>
              <Route path="/endpoint/:endpointId" element={<EndpointView />} />
              <Route path="/edit-dag/:dagId/:project/:env" element={<DagEditView />} />
              <Route path="/" element={<Navigate to="/endpoint/get-dags" replace />} />
            </Routes>
          </Col>
        </Row>
      </Container>
    </Router>
  );
}

export default App;