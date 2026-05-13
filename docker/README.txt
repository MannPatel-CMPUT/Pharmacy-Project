Pharmacy stack — Docker (API + Ollama on one machine)

Build and run:
  docker compose build
  docker compose up -d

Pull a model into Ollama (once per machine/volume):
  docker compose exec ollama ollama pull llama3

Open app (Pharma Checker + pharmacy workspace on one port):
  http://localhost:8000
  (Splash → sign up / sign in / forgot password → /workspace dashboard. React shell is built into the `api` image.)

If the UI looks old after you changed frontend/ (hard refresh not enough):
  From the repo root (where docker-compose.yml lives):
    docker compose build --no-cache api
    docker compose up -d --force-recreate api
  Confirm the new HTML is inside the container:
    docker compose exec api grep -n "Assigned to" /app/frontend/index.html
  (Should print a line number; if "no matches", the image was built from the wrong folder.)

Ollama API (from host, for debugging):
  http://localhost:11434

Environment:
  API uses OLLAMA_BASE_URL=http://ollama:11434 inside the compose network.
  SQLite DB persists in Docker volume "pharmacy_data" at /data inside the api container.

Large interaction CSV:
  Mount your db_drug_interactions.csv and set DRUG_INTERACTIONS_CSV in docker-compose.yml
  (see commented example).

Note:
  Counseling in this repo is template-based by default. Ollama is available on the
  same network when you add optional LLM features that call OLLAMA_BASE_URL.

GPU (Linux + NVIDIA):
  Uncomment the deploy.resources section under the ollama service in docker-compose.yml.
