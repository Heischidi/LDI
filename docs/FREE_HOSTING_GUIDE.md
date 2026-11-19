# Free ($0/month) Cloud Deployment Guide — Option 1

This guide deploys **Leaders Document Intelligence (LDI)** at **$0/month** across managed free tiers using the repository configuration:

- **Frontend (`apps/web`)**: Vercel Hobby (free)
- **Backend API (`apps/api`)**: Render Free Docker Web Service (configured in [`render.yaml`](../render.yaml))
- **PostgreSQL Database**: Neon Free Tier (0.5 GB storage, serverless Postgres)
- **Private Document Vault**: Neon Object Storage (`assets` private bucket provisioned by `neon.ts`) — or Cloudflare R2 (10 GB/month free, $0 egress)
- **Async Worker Mode**: Built-in eager/in-process thread execution (`CELERY_ALWAYS_EAGER=true`, no Redis or 2nd worker container needed)
- **OCR & AI**: Free built-in `TESSERACT` inside the Docker image + `LOCAL_DETERMINISTIC` classifier (or switch `AI_PROVIDER=GEMINI` + `ALLOW_EXTERNAL_AI=true` with a free Google AI Studio API key)

> **Why not host `apps/api` on Vercel too?**  
> Vercel Serverless Functions have a 250 MB bundle ceiling, lack the `tesseract-ocr` / `poppler-utils` system binaries, wipe `/tmp` between invocations, and freeze background CPU after an HTTP response returns. Hosting only `apps/web` on Vercel and `apps/api` as a single free Docker container on Render keeps everything persistent and $0/month.

---

## Step 1 — Push Repository to GitHub

Commit and push this workspace to a private or public GitHub repository so Vercel and Render can deploy automatically.

---

## Step 2 — Provision Neon PostgreSQL & Object Storage (`neon.ts`)

1. Sign up at [neon.tech](https://neon.tech) and link/provision via CLI (`neon init` + `neon deploy`), which uses [`neon.ts`](../neon.ts) and populates `.env.local` with:
   - `DATABASE_URL` (pooled runtime connection) and `DATABASE_URL_UNPOOLED` (direct connection for Alembic migrations)
   - `AWS_ENDPOINT_URL_S3`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` for Neon Object Storage (`assets` private bucket)
2. LDI's backend config ([`config.py`](../apps/api/app/core/config.py)) automatically:
   - Converts `postgres://` and `postgresql://` into `postgresql+psycopg://` for SQLAlchemy 2.0 + `psycopg` v3.
   - Enables `pool_pre_ping=True` and `pool_recycle=300` in [`database.py`](../apps/api/app/core/database.py).
   - Maps Neon's `AWS_*` storage variables and enables S3 path-style addressing (`force_path_style`) for boto3.

---

## Step 3 — Deploy Backend API on Render (`render.yaml`)

1. Sign in at [render.com](https://render.com) → **New +** → **Blueprint**.
2. Connect your GitHub repository; Render automatically detects [`render.yaml`](../render.yaml) (`ldi-api` service using `./infrastructure/docker/Dockerfile.api`, Ohio region matching Neon `us-east-2`, free plan).
3. Provide values from your Neon `.env.local` when prompted for the `sync: false` variables:
   - `DATABASE_URL` & `DATABASE_URL_UNPOOLED`: From `.env.local`
   - `S3_ENDPOINT_URL`: Value of `AWS_ENDPOINT_URL_S3` from `.env.local`
   - `S3_ACCESS_KEY_ID`: Value of `AWS_ACCESS_KEY_ID` from `.env.local`
   - `S3_SECRET_ACCESS_KEY`: Value of `AWS_SECRET_ACCESS_KEY` from `.env.local`
   - `CORS_ORIGINS`: Temporary placeholder `http://localhost:3000` (update in Step 5 once Vercel gives you your live domain)
   - `GEMINI_API_KEY`: Optional (leave empty while `AI_PROVIDER=LOCAL_DETERMINISTIC`, or set `AI_PROVIDER=GEMINI`, `ALLOW_EXTERNAL_AI=true`, and paste your Gemini key)
4. Wait for the Render Docker build & `/health` check to turn **Live**, then copy your Render URL (e.g. `https://ldi-api.onrender.com`).

> **Note on Render Free Tier:** Free services spin down after 15 minutes of inactivity and take ~30–50 seconds to wake up on the first request. All data and files stay safely stored in Neon PostgreSQL and Neon Object Storage across restarts.

---

## Step 4 — Deploy Frontend on Vercel

1. Sign in at [vercel.com](https://vercel.com) → **Add New Project** → import the same GitHub repository.
2. In **Configure Project**:
   - **Root Directory**: `apps/web`
   - **Framework Preset**: Next.js (auto-detected)
   - Add **Environment Variable**:
     - `NEXT_PUBLIC_API_URL` = `https://ldi-api.onrender.com`
3. Deploy and copy your live Vercel URL (e.g. `https://leaders-doc-intel.vercel.app`).

---

## Step 5 — Link CORS & Change Default Passwords

1. In Render → `ldi-api` → **Environment**, set:
   - `CORS_ORIGINS` = `https://<YOUR-VERCEL-DOMAIN>.vercel.app,http://localhost:3000`
2. Save changes (Render restarts with the updated CORS origin).
3. Open your live Vercel URL and sign in with the default Super Admin (`superadmin@leaders.edu` / `LeadersAdmin!2026`), then **immediately reset all default staff passwords** in Staff Management for production security.
