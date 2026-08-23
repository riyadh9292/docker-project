# Monitoring App — Dashboard + Collector

## Task 1 — Linux setup (run these on the Poridhi Lab VM)

```bash
mkdir -p ~/docker-project/dashboard ~/docker-project/collector
cd ~/docker-project

# Environment checks
uname -a          # kernel / architecture
ip addr            # find the server's IP (needed for http://<server-ip>:9090)
df -h               # confirm free disk space before pulling images
ls -l               # confirm file permissions on the files you just copied in
```

Copy `dashboard/index.html`, `dashboard/nginx.conf`, `dashboard/Dockerfile`,
`collector/app.py`, `collector/Dockerfile`, and `compose.yaml` from this
project into the matching folders on the lab VM.

## Task 2 & 3 — Build and run manually (before using Compose)

```bash
# Pull base images explicitly so you can see them with `docker images`
docker pull nginx:alpine
docker pull python:3.12-slim

# Build both images
docker build -t monitoring-dashboard:latest ./dashboard
docker build -t monitoring-collector:latest ./collector

# Create the network the two services will share
docker network create monitoring-net

# Create the volume for persistent collector data
docker volume create collector-data

# Run the collector first (dashboard depends on it)
docker run -d --name collector \
  --network monitoring-net \
  -v collector-data:/data \
  monitoring-collector:latest

# Run the dashboard, publishing 9090 on the host -> 80 in the container
docker run -d --name dashboard \
  --network monitoring-net \
  -p 9090:80 \
  monitoring-dashboard:latest

# Verify
docker images
docker ps
docker network ls
docker network inspect monitoring-net
docker volume ls
docker volume inspect collector-data
curl http://localhost:9090/api/status
```

Note the containers talk to each other as `collector` and `dashboard`
(the container/service names) — never a hard-coded container IP. That
resolution only works because both are on the same user-defined bridge
network (`monitoring-net`); containers on Docker's default bridge network
do **not** get automatic DNS resolution by name.

## Task 4 — Docker Compose

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
```

Open `http://<server-ip>:9090` in a browser — the dashboard polls
`/api/status` every 5 seconds, which nginx proxies to the collector.

Check the collector directly:

```bash
curl http://<server-ip>:9090/api/status
docker compose exec collector cat /data/access.log
```

## Task 5 — Monitoring & troubleshooting

```bash
docker ps
docker logs dashboard
docker logs collector
docker inspect dashboard
docker stats --no-stream
docker network inspect monitoring-net
ss -tulnp | grep 9090
```

### Example issue encountered while building this

**Problem:** After running `docker compose up -d`, the dashboard loaded in
the browser, but the metrics card showed "Disconnected" and the error
`502 Bad Gateway` from nginx.

**How it was found:** `docker logs dashboard` showed nginx errors of the
form `connect() failed (111: Connection refused) while connecting to
upstream, upstream: "http://collector:6000/..."`. `docker compose ps`
confirmed the `collector` container was still `Restarting`.
`docker logs collector` then showed a Python traceback — the app was
trying to write to `/data/access.log` before the directory existed.

**Fix:** Added `os.makedirs(DATA_DIR, exist_ok=True)` at startup in
`app.py` (see `ensure_data_dir()`), and made sure the `collector-data`
volume is declared in `compose.yaml` before the collector service tries
to use it. After rebuilding (`docker compose up -d --build`), the
collector stayed `Up`, and `curl http://localhost:9090/api/status`
returned a valid JSON payload.

## Short Questions

**1. Difference between a Docker image and a container?**
An image is a read-only, versioned template (filesystem + metadata)
built from a Dockerfile — it doesn't run on its own. A container is a
running (or stopped) *instance* of an image, with its own writable
layer, process space, and network namespace. One image can produce
many independent containers.

**2. What does `9090:80` mean?**
It's a host-to-container port mapping in the form `HOST_PORT:CONTAINER_PORT`.
Traffic hitting the host machine on port 9090 gets forwarded by Docker's
network proxy to port 80 inside the container, where nginx is listening.
The container's internal port (80) never needs to match the externally
exposed one.

**3. Why do containers need a Docker network?**
By default, containers are isolated from each other. A shared
user-defined network gives them a private virtual network plus
built-in DNS, so they can reach each other by container/service name
(e.g., `collector`) instead of hard-coded, easily-changing IP
addresses, while staying isolated from unrelated containers.

**4. Why do we use Docker volumes?**
A container's writable layer is deleted when the container is removed.
Volumes are storage managed by Docker outside any single container's
lifecycle, so data (here, the collector's `access.log`) survives
container restarts, rebuilds, or replacement, and can optionally be
shared between containers.

**5. What problem does Docker Compose solve?**
It replaces a series of manual `docker build` / `docker network create`
/ `docker volume create` / `docker run` commands with one declarative
YAML file. `docker compose up -d` builds and starts every service with
the right networks, volumes, ports, and dependencies in one command,
making the whole multi-container app reproducible and easy to tear
down (`docker compose down`).

## Bonus — restart policy

Both services use `restart: unless-stopped` in `compose.yaml`. This
tells the Docker daemon to automatically restart the container if it
crashes or the host reboots, *unless* someone explicitly stopped it
with `docker stop` / `docker compose stop` — in which case Docker
leaves it stopped rather than fighting the operator. This gives the
monitoring stack resilience against crashes without overriding a
deliberate shutdown.
