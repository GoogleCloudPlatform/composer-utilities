# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Stage 1: Build the React frontend
FROM node:20-alpine AS builder
WORKDIR /app

# Copy package.json and package-lock.json
COPY package.json ./

# Install dependencies
RUN npm install

# Copy the rest of the frontend source code
COPY public ./public
COPY src ./src

# Build the React app
RUN npm run build

# Stage 2: Create the final production image
FROM python:3.12-slim
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python backend and environment config
COPY proxy_server.py .

# Copy the built React app from the builder stage
COPY --from=builder /app/build ./build

# Expose the port Gunicorn will run on
# Cloud Run provides the PORT environment variable, default is 8080
EXPOSE 8080

# Start Gunicorn
# The PORT environment variable is automatically set by Cloud Run.
CMD exec uvicorn proxy_server:app --host 0.0.0.0 --port $PORT
