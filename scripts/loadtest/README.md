# Load testing the production droplet

`sla-test.js` is a [k6](https://k6.io) script that reproduces the three map-read cases derived in
the final report (§8 Performance) — warm-cache best case, mid-zoom average case, cold-cache
antimeridian worst case — plus entity-detail reads and fuzzy search. Its thresholds *are* the
report's SLA targets, so a run directly produces (or fails) the numbers for the report's
"Performance ranges" table and resolves its `[TBD: confirm on production hardware]` markers.

## Ground rules (read first)

- **Never run the generator on the droplet itself** — it competes with FrankenPHP and Postgres
  for the same cores and invalidates the numbers. Run from your dev machine, a second small
  droplet in the same region (best signal), or a cloud runner.
- **Hit the origin directly.** If Cloudflare (or any CDN) is ever put in front of the site, do
  NOT load-test through it — it violates Cloudflare's ToS and their cache distorts results.
  Test the droplet IP / a grey-clouded hostname instead.
- **Own infrastructure only, off-peak, snapshot first.** Testing your own droplet is fine under
  DigitalOcean's acceptable-use policy. Take a droplet snapshot before the first big run.
- The script only issues **GET** requests against public read endpoints — no writes, no auth.

## Option A — run from your local machine

1. Install k6 (single binary):
   - Debian/Ubuntu: `sudo gpg -k && sudo apt-get install k6` (after adding the
     [k6 apt repo](https://grafana.com/docs/k6/latest/set-up/install-k6/)), or just download the
     binary: `curl -L https://github.com/grafana/k6/releases/latest/download/k6-v1.0.0-linux-amd64.tar.gz | tar xz`
   - macOS: `brew install k6`
   - Windows: `winget install k6 --source winget`
2. Smoke run (1–2 minutes, tiny load — verify endpoints and dataset first):

   ```bash
   k6 run -e BASE_URL=https://YOUR-DROPLET -e TARGET_VUS=3 -e DURATION=1m \
     scripts/loadtest/sla-test.js
   ```

3. Real run (defaults: ramp to 30 VUs, 3-minute plateau):

   ```bash
   k6 run -e BASE_URL=https://YOUR-DROPLET \
     --summary-export=loadtest-summary.json \
     scripts/loadtest/sla-test.js
   ```

4. Capacity probe: re-run with `-e TARGET_VUS=60`, `=100`, … until a threshold fails. The last
   passing level is your capacity figure; note it in the report alongside the latency table.

Caveat: from a home connection, your last-mile latency and bandwidth are part of every number.
Fine for p95-vs-target verdicts; for clean server-side numbers use Option B.

## Option B — run from a second droplet in the same region (best numbers)

```bash
# 1. Create a minimal runner in the SAME region as production (e.g. $6/mo, then destroy)
doctl compute droplet create k6-runner --region <same-region> --size s-1vcpu-1gb \
  --image ubuntu-24-04-x64 --ssh-keys <your-key-id>

# 2. SSH in, install k6, copy the script
scp scripts/loadtest/sla-test.js root@RUNNER_IP:
ssh root@RUNNER_IP
curl -L https://github.com/grafana/k6/releases/latest/download/k6-v1.0.0-linux-amd64.tar.gz \
  | tar xz --strip-components=1
./k6 run -e BASE_URL=https://YOUR-DROPLET --summary-export=summary.json sla-test.js

# 3. Copy summary.json back, destroy the runner
doctl compute droplet delete k6-runner
```

Same-region datacenter-to-datacenter latency is sub-millisecond, so the measured durations are
effectively pure server time — the honest values for the report's SLA table.

## Option C — Grafana Cloud k6 (hosted cloud runner)

Grafana Cloud's free tier includes hosted k6 runs (no infrastructure of your own):

```bash
k6 cloud login          # one-time; free Grafana Cloud account
k6 cloud run -e BASE_URL=https://YOUR-DROPLET scripts/loadtest/sla-test.js
```

You get a hosted dashboard with per-scenario percentiles and threshold verdicts. Choose a load
zone geographically near the droplet for server-focused numbers, or far away to measure the
reader experience. Mind the free-tier quota (limited virtual-user-hours per month) — do smoke
runs locally and save cloud runs for the real measurements.

## What to watch during the run

- **DigitalOcean droplet graphs** (control panel → droplet → Graphs): CPU, memory, bandwidth.
  The first bottleneck is usually Postgres CPU on the `map-worst` scenario.
- **Per-container split** over SSH: `docker stats` — separates app vs Postgres vs Redis load.
- **k6 output**: per-scenario `http_req_duration` min/med/p95/p99/max lines and the
  threshold ✓/✗ verdicts at the end.

## Mapping results into the report

From the end-of-run summary (or `loadtest-summary.json`):

| k6 tag           | Report row                       | Columns                      |
|------------------|----------------------------------|------------------------------|
| `entity-detail`  | Entity detail read               | min→Best, med/avg→Average, p99→Worst |
| `map-warm`       | Map bbox + year read (best)      | Best                         |
| `map-average`    | Map bbox + year read (average)   | Average                      |
| `map-worst`      | Map bbox + year read (worst)     | Worst                        |
| `search`         | Fuzzy entity search              | min / med / p99              |
| `http_req_failed`| availability check               | must stay < 0.5%             |

Replace the `[TBD: confirm on production hardware]` markers in
`output/cs423/final-report/sections/08-outcomes-evaluation.tex`, note the peak VU level and
date, and recompile (`./compile.sh` in the report folder).

## Knobs

| Env var      | Default | Meaning                                  |
|--------------|---------|------------------------------------------|
| `BASE_URL`   | —       | Target origin (required)                 |
| `TARGET_VUS` | `30`    | Peak virtual users, split across scenarios |
| `DURATION`   | `3m`    | Plateau length at peak                   |
