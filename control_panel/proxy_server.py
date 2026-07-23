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

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

# Disable mutual TLS (mTLS) to prevent urllib3/pyopenssl context mutation errors
os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"


import google.auth
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import storage  # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO)

# Global variables
storage_client = None
http_client = None
google_credentials = None

ENV_CACHE_TTL = 300
cached_environments = None
last_env_fetch_time = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global storage_client, http_client, google_credentials

    # Initialize global clients
    try:
        google_credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    except Exception as e:
        logging.error(f"Error getting default Google credentials: {e}")
        # Will fallback and error locally if it doesn't work

    try:
        # Build these synchronously once on startup
        import socket

        socket.setdefaulttimeout(60)
        storage_client = storage.Client()
    except Exception as e:
        logging.error(f"Error building global Google API clients: {e}")

    # Initialize shared async HTTP client
    http_client = httpx.AsyncClient(timeout=300.0)

    yield  # Let the app run

    # Cleanup
    await http_client.aclose()


app = FastAPI(lifespan=lifespan)

# Restrict CORS here appropriately
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
# If we have an environment variable for origins, we can parse it
allowed_origins = os.environ.get("ALLOWED_ORIGINS")
if allowed_origins:
    origins.extend(allowed_origins.split(","))

# Or to allow all (not recommended, but if necessary):
# origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Be explicit instead of "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_gcp_project_id():
    _, project_id = google.auth.default()
    if not project_id and google_credentials:
        project_id = getattr(google_credentials, "quota_project_id", None)
    if not project_id:
        try:
            import subprocess

            project_id = subprocess.check_output(
                ["gcloud", "config", "get-value", "project"], text=True
            ).strip()
        except Exception:
            pass
    return project_id


async def get_valid_token():
    """Lazily refresh the google credentials to ensure we have a valid token."""
    global google_credentials
    if not google_credentials:
        return None

    if not google_credentials.valid:
        # refresh() is blocking (network call via urllib3/requests), so we run it in executor
        await asyncio.to_thread(google_credentials.refresh, GoogleAuthRequest())

    return google_credentials.token


async def get_all_environments_async():
    global cached_environments, last_env_fetch_time
    current_time = time.time()

    if (
        cached_environments is not None
        and (current_time - last_env_fetch_time) < ENV_CACHE_TTL
    ):
        return cached_environments

    token = await get_valid_token()
    if not token:
        logging.error("Failed to get valid token for environment fetch")
        return cached_environments if cached_environments is not None else []

    headers = {"Authorization": f"Bearer {token}"}

    projects_str = os.environ.get("COMPOSER_PROJECTS", "")
    if projects_str:
        projects = [p.strip() for p in projects_str.split(",") if p.strip()]
    else:
        project_id = get_gcp_project_id()
        if not project_id:
            logging.error("Google Cloud project ID could not be determined.")
            return cached_environments if cached_environments is not None else []
        projects = [project_id]

    locations_str = os.environ.get("COMPOSER_LOCATIONS", "us-central1,us-east4")
    locations = [loc.strip() for loc in locations_str.split(",") if loc.strip()]

    discovered_envs = []

    for project in projects:
        for loc in locations:
            try:
                url = f"https://composer.googleapis.com/v1/projects/{project}/locations/{loc}/environments"
                resp = await http_client.get(url, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    envs = data.get("environments", [])
                    for env in envs:
                        name = env["name"].split("/")[-1]
                        config = env.get("config", {})
                        url_val = config.get("airflowUri", "")
                        bucket_prefix = config.get("dagGcsPrefix", "")

                        software_config = config.get("softwareConfig", {})
                        image_version = software_config.get("imageVersion", "")

                        if url_val:
                            discovered_envs.append(
                                {
                                    "name": name,
                                    "url": url_val,
                                    "project": project,
                                    "location": loc,
                                    "bucket": bucket_prefix.split("/")[2]
                                    if bucket_prefix
                                    else None,
                                    "imageVersion": image_version,
                                }
                            )
                else:
                    logging.error(
                        f"Error fetching environments for project {project} location {loc}: {resp.status_code} - {resp.text}"
                    )
            except Exception as e:
                logging.error(
                    f"Exception fetching environments for project {project} location {loc}: {e}"
                )

    discovered_envs.sort(key=lambda x: x["name"])

    if discovered_envs:
        cached_environments = discovered_envs
        last_env_fetch_time = current_time
        return cached_environments

    if cached_environments is not None:
        logging.warning("Returning stale cached environments due to fetch error.")
        return cached_environments
    return []


@app.get("/api/environments")
async def get_environments():
    return await get_all_environments_async()


async def fetch_environment_details_async(project, location, name):
    try:
        token = await get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://composer.googleapis.com/v1/projects/{project}/locations/{location}/environments/{name}"
        resp = await http_client.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        else:
            logging.error(
                f"Error fetching details for {name}: {resp.status_code} - {resp.text}"
            )
            return None
    except Exception as e:
        logging.error(f"Exception fetching details for {name}: {e}")
        return None


@app.get("/api/environments/{name}/details")
async def get_environment_details_route(name: str):
    environments = await get_all_environments_async()
    environment = next((env for env in environments if env["name"] == name), None)
    if not environment:
        raise HTTPException(status_code=400, detail="Invalid environment name.")

    details = await fetch_environment_details_async(
        environment["project"], environment["location"], name
    )

    if details:
        return details
    raise HTTPException(status_code=500, detail="Failed to fetch environment details")


async def fetch_dags_and_errors_for_environment(env, token, query_params):
    """Fetches DAGs and import errors for an environment asynchronously."""
    try:
        bucket = env.get("bucket")
        if not bucket:
            # Fallback if bucket wasn't cached during list
            details = await fetch_environment_details_async(
                env["project"], env["location"], env["name"]
            )
            if details:
                bucket = details["config"]["dagGcsPrefix"].split("/")[2]
                env["bucket"] = bucket

        headers = {"Authorization": f"Bearer {token}"}

        image_version = env.get("imageVersion", "")
        api_version = "v2" if "-airflow-3" in image_version else "v1"

        # Parallel async requests!
        dags_url = f"{env['url']}/api/{api_version}/dags"
        errors_url = f"{env['url']}/api/{api_version}/importErrors"
        dag_runs_url = f"{env['url']}/api/{api_version}/dags/~/dagRuns"

        dag_runs_params = {"limit": 100}
        if api_version == "v2":
            dag_runs_params["order_by"] = "-logical_date"
        else:
            dag_runs_params["order_by"] = "-execution_date"

        dags_task = http_client.get(dags_url, headers=headers, params=query_params)
        errors_task = http_client.get(errors_url, headers=headers)
        dag_runs_task = http_client.get(
            dag_runs_url, headers=headers, params=dag_runs_params
        )

        dags_res, errors_res, dag_runs_res = await asyncio.gather(
            dags_task, errors_task, dag_runs_task, return_exceptions=True
        )

        dag_runs_data = []
        if not isinstance(dag_runs_res, Exception) and dag_runs_res.status_code == 200:
            dag_runs_data = dag_runs_res.json().get("dag_runs", [])

        runs_by_dag = {}
        for run in dag_runs_data:
            d_id = run.get("dag_id")
            if d_id not in runs_by_dag:
                runs_by_dag[d_id] = []
            runs_by_dag[d_id].append(
                {
                    "dag_run_id": run.get("dag_run_id"),
                    "state": run.get("state"),
                    "execution_date": run.get("execution_date")
                    or run.get("logical_date"),
                }
            )

        dags_data = []
        if not isinstance(dags_res, Exception) and dags_res.status_code == 200:
            dags_data = dags_res.json().get("dags", [])
            for dag in dags_data:
                dag["environment"] = env
                dag["bucket"] = bucket
                dag["last_runs"] = runs_by_dag.get(dag["dag_id"], [])[:5]

        import_errors_data = []
        if not isinstance(errors_res, Exception) and errors_res.status_code == 200:
            import_errors_data = errors_res.json().get("import_errors", [])
            for error in import_errors_data:
                error["environment"] = env

        return {"dags": dags_data, "import_errors": import_errors_data}

    except Exception as e:
        logging.error(f"Error fetching data for {env['name']}: {e}")
        return {"dags": [], "import_errors": []}


@app.get("/api/all-dags")
async def get_all_dags_concurrently(request: Request):
    token = await get_valid_token()
    if not token:
        raise HTTPException(status_code=500, detail="Google Authentication Failed")

    environments = await get_all_environments_async()
    query_params = dict(request.query_params)

    # Launch all environment fetches concurrently using asyncio.gather
    tasks = [
        fetch_dags_and_errors_for_environment(env, token, query_params)
        for env in environments
    ]
    results = await asyncio.gather(*tasks)

    all_dags = []
    all_import_errors = []
    for res in results:
        all_dags.extend(res["dags"])
        all_import_errors.extend(res["import_errors"])

    return {"dags": all_dags, "import_errors": all_import_errors}


def get_dag_content_sync(bucket_name, file_path):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    return blob.download_as_string()


def update_dag_content_sync(bucket_name, file_path, content):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    blob.upload_from_string(content)


def sanitize_filename(filename: str | None, default_dag_id: str | None = None) -> str:
    if filename:
        if filename.startswith("/home/airflow/gcs/"):
            filename = filename.replace("/home/airflow/gcs/", "", 1)
        if not filename.startswith("dags/"):
            filename = f"dags/{filename}"
        # Prevent path traversal
        if ".." in filename:
            raise HTTPException(status_code=400, detail="Invalid filename format.")
        return filename

    if default_dag_id:
        return f"dags/{default_dag_id}.py"

    raise HTTPException(status_code=400, detail="Filename or dag_id required.")


@app.get("/api/dags/{dag_id}/content")
async def get_dag_content(dag_id: str, request: Request, filename: str | None = None):
    env_header: str | None = request.headers.get("X-Composer-Environment")
    if not env_header:
        raise HTTPException(
            status_code=400, detail="X-Composer-Environment header is required."
        )

    env_url = env_header.rstrip("/")
    environments = await get_all_environments_async()
    environment = next(
        (env for env in environments if env["url"].rstrip("/") == env_url), None
    )

    if not environment:
        raise HTTPException(status_code=400, detail="Invalid environment URL.")

    # Get bucket directly from cached env
    bucket_name = environment.get("bucket")
    if not bucket_name:
        details = await fetch_environment_details_async(
            environment["project"], environment["location"], environment["name"]
        )
        bucket_name = details["config"]["dagGcsPrefix"].split("/")[2]

    file_path = sanitize_filename(filename, dag_id)

    try:
        content = await asyncio.to_thread(get_dag_content_sync, bucket_name, file_path)
        return Response(content=content, media_type="text/plain")
    except Exception as e:
        logging.error(f"Error fetching DAG content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dags/{dag_id}/content")
async def update_dag_content(
    dag_id: str, request: Request, filename: str | None = None
):
    env_header: str | None = request.headers.get("X-Composer-Environment")
    if not env_header:
        raise HTTPException(
            status_code=400, detail="X-Composer-Environment header is required."
        )

    data = await request.json()
    content = data.get("content")
    if content is None:
        raise HTTPException(
            status_code=400, detail="Missing 'content' in request body."
        )

    # Dry-run Python syntax validation
    import ast

    try:
        ast.parse(content, filename=filename or f"{dag_id}.py")
    except SyntaxError as e:
        logging.error(f"Syntax error in submitted DAG code: {e}")
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"SyntaxError: {e.msg}",
                "line": e.lineno,
                "offset": e.offset,
                "text": e.text,
            },
        )

    env_url = env_header.rstrip("/")
    environments = await get_all_environments_async()
    environment = next(
        (env for env in environments if env["url"].rstrip("/") == env_url), None
    )

    if not environment:
        raise HTTPException(status_code=400, detail="Invalid environment URL.")

    bucket_name = environment.get("bucket")
    if not bucket_name:
        details = await fetch_environment_details_async(
            environment["project"], environment["location"], environment["name"]
        )
        bucket_name = details["config"]["dagGcsPrefix"].split("/")[2]

    file_path = sanitize_filename(filename, dag_id)

    try:
        await asyncio.to_thread(
            update_dag_content_sync, bucket_name, file_path, content
        )
        return {"message": "DAG content updated successfully."}
    except Exception as e:
        logging.error(f"Error updating DAG content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def reparse_dag_sync(bucket_name, file_path):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    if not blob.exists():
        raise Exception(f"File {file_path} not found in GCS bucket.")
    content = blob.download_as_string()
    blob.upload_from_string(content)


@app.post("/api/dags/{dag_id}/reparse")
async def reparse_dag(dag_id: str, request: Request, filename: str | None = None):
    env_header: str | None = request.headers.get("X-Composer-Environment")
    if not env_header:
        raise HTTPException(
            status_code=400, detail="X-Composer-Environment header is required."
        )

    env_url = env_header.rstrip("/")
    environments = await get_all_environments_async()
    environment = next(
        (env for env in environments if env["url"].rstrip("/") == env_url), None
    )

    if not environment:
        raise HTTPException(status_code=400, detail="Invalid environment URL.")

    bucket_name = environment.get("bucket")
    if not bucket_name:
        details = await fetch_environment_details_async(
            environment["project"], environment["location"], environment["name"]
        )
        bucket_name = details["config"]["dagGcsPrefix"].split("/")[2]

    file_path = sanitize_filename(filename, dag_id)

    try:
        await asyncio.to_thread(reparse_dag_sync, bucket_name, file_path)
        return {"message": "DAG file touched successfully. Reparsing triggered."}
    except Exception as e:
        logging.error(f"Error touching DAG file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.api_route(
    "/api/{api_version}/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"]
)
async def proxy(api_version: str, path: str, request: Request):
    """Forwards requests to the Airflow API."""
    env_header: str | None = request.headers.get("X-Composer-Environment")
    if not env_header:
        raise HTTPException(
            status_code=400, detail="X-Composer-Environment header is required."
        )

    token = await get_valid_token()
    if not token:
        raise HTTPException(status_code=500, detail="Google Authentication Failed")

    airflow_url = f"{env_header.rstrip('/')}/api/{api_version}/{path}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ["host", "content-length", "x-composer-environment"]
    }
    headers["Authorization"] = f"Bearer {token}"

    try:
        req_body = await request.body()
        assert http_client is not None
        resp = await http_client.request(
            method=request.method,
            url=airflow_url,
            headers=headers,
            params=request.query_params.multi_items(),
            content=req_body,
        )

        excluded_headers = [
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection",
        ]
        resp_headers = {
            k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers
        }

        return Response(
            content=resp.content, status_code=resp.status_code, headers=resp_headers
        )

    except httpx.RequestError as e:
        logging.error(f"Request Forwarding Error: {repr(e)}")
        raise HTTPException(status_code=500, detail=f"Proxy server error: {repr(e)}")


# Serve React App
# Note: In FastAPI, defining a catch-all route that handles directories must be done carefully.
# If `build/static` and `build` exist, we can mount `StaticFiles`.
if os.path.exists("build/static"):
    app.mount("/static", StaticFiles(directory="build/static"), name="static")


@app.get("/{path:path}")
async def serve_react_app(path: str):
    # Try serving a file from the build folder if it exists
    base_path = os.path.abspath("build")
    filepath = os.path.normpath(os.path.join(base_path, path))
    if path and filepath.startswith(base_path) and os.path.exists(filepath):
        from fastapi.responses import FileResponse

        return FileResponse(filepath)
    # Default to index.html for unknown routes (React SPA)
    if os.path.exists(os.path.join("build", "index.html")):
        from fastapi.responses import FileResponse

        return FileResponse(os.path.join("build", "index.html"))

    # If build directory doesn't exist, we fallback
    return {"message": "Server running, but frontend build not found."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3001)
