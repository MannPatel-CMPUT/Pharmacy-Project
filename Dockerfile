# Build PairWise Rx React shell (served by FastAPI on :8000)
FROM node:20-bookworm-slim AS portal_build
WORKDIR /pb
COPY portal/package.json ./
COPY portal/client ./client
COPY portal/server ./server
RUN npm install && npm run build

# Pharmacy API + static frontends
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/fastapi

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY fastapi/ /app/fastapi/
COPY frontend/ /app/frontend/
COPY --from=portal_build /pb/client/dist /app/portal/client/dist

WORKDIR /app/fastapi

ENV DATABASE_URL=sqlite:////data/pharmacy.db

# Render and other hosts set PORT; default 8000 for local `docker run` without -p semantics.
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
