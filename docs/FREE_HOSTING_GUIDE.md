# Free ($0/month) Cloud Deployment Guide — Option 1

This guide deploys **Leaders Document Intelligence (LDI)** at **$0/month** across managed free tiers using the repository configuration:

- **Frontend (`apps/web`)**: Vercel Hobby (free)
- **Backend API (`apps/api`)**: Render Free Docker Web Service (configured in [`render.yaml`](../render.yaml))
- **PostgreSQL Database**: Neon Free Tier (0.5 GB storage, serverless Postgres)
- **Private Document Vault**: Cloudflare R2 Free Tier (10 GB/month storage, $0 egress)
- **Async Worker Mode**: Built-in eager/in-process thread execution (`CELERY_ALWAYS_EAGER=true`, no Redis or 2nd worker container needed)
- **OCR & AI**: Free built-in `TESSERACT` inside the Docker image + `LOCAL_DETERMINISTIC` classifier (or switch `AI_PROVIDER=GEMINI` + `ALLOW_EXTERNAL_AI=true` with a free Google AI Studio API key)

> **Why not host `apps/api` on Vercel too?**  
> Vercel Serverless Functions have a 250 MB bundle ceiling, lack the `tesseract-ocr` / `poppler-utils` system binaries, wipe `/tmp` between invocations, and freeze background CPU after an HTTP response returns. Hosting only `apps/web` on Vercel and `apps/api` as a single free Docker container on Render keeps everything persistent and $0/month.

---

## Step 1 — Push Repository to GitHub

Commit and push this workspace to a private or public GitHub repository so Vercel and Render can deploy automatically.

---

## Step 2 — Create Free PostgreSQL Database (Neon)

1. Sign up at [neon.tech](https://neon.tech) (free tier, no credit card required).
2. Create a project (e.g. `ldi-production`, region close to your users such as EU Frankfurt).
3. Copy the **Connection String** (e.g. `postgresql://user:pass@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`).
   - LDI's backend config ([`config.py`](../apps/api/app/core/config.py)) automatically converts `postgres://` and `postgresql://` into `postgresql+psycopg://` for SQLAlchemy 2.0 + `psycopg` v3.

---

## Step 3 — Create Free S3 Object Storage Bucket (Cloudflare R2)

1. Sign in to the Cloudflare Dashboard → **R2 Object Storage**.
2. Create a private bucket (e.g. `ldi-documents-private`).
3. Create an **R2 API Token** with **Object Read & Write** permissions for that bucket.
4. Record:
   - `S3_ENDPOINT_URL`: `https://<YOUR_CLOUDFLARE_ACCOUNT_ID>.r2.cloudflarestorage.com`
   - `S3_BUCKET_NAME`: `ldi-documents-private`
   - `S3_ACCESS_KEY_ID` & `S3_SECRET_ACCESS_KEY`
   - `S3_REGION`: `auto`

---

## Step 4 — Deploy Backend API on Render (`render.yaml`)

1. Sign in at [render.com](https://render.com) → **New +** → **Blueprint**.
2. Connect your GitHub repository; Render automatically detects [`render.yaml`](../render.yaml) (`ldi-api` service using `./infrastructure/docker/Dockerfile.api`, free plan).
3. Provide values when prompted for the `sync: false` variables:
   - `DATABASE_URL`: Neon PostgreSQL connection string from Step 2
   - `CORS_ORIGINS`: Temporary placeholder `http://localhost:3000` (you will update this in Step 6 once Vercel gives you your live domain)
   - `S3_ENDPOINT_URL`, `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`: Cloudflare R2 values from Step 3
   - `GEMINI_API_KEY`: Optional (leave empty while `AI_PROVIDER=LOCAL_DETERMINISTIC`, or set `AI_PROVIDER=GEMINI`, `ALLOW_EXTERNAL_AI=true`, and paste your Gemini key)
4. Wait for the Render Docker build & `/health` check to turn **Live**, then copy your Render URL (e.g. `https://ldi-api.onrender.com`).

> **Note on Render Free Tier:** Free services spin down after 15 minutes of inactivity and take ~30–50 seconds to wake up on the first request. All data and files stay safely stored in Neon PostgreSQL and Cloudflare R2 across restarts.

---

## Step 5 — Deploy Frontend on Vercel

1. Sign in at [vercel.com](https://vercel.com) → **Add New Project** → import the same GitHub repository.
2. In **Configure Project**:
   - **Root Directory**: `apps/web`
   - **Framework Preset**: Next.js (auto-detected)
   - Add **Environment Variable**:
     - `NEXT_PUBLIC_API_URL` = `https://<YOUR-RENDER-SERVICE>.onrender.com/api`
3. Deploy and copy your live Vercel URL (e.g. `https://leaders-doc-intel.vercel.app`).

---

## Step 6 — Link CORS & Change Default Passwords

1. In Render → `ldi-api` → **Environment**, set:
   - `CORS_ORIGINS` = `https://<YOUR-VERCEL-DOMAIN>.vercel.app,http://localhost:3000`
2. Save changes (Render restarts with the updated CORS origin).
3. Open your live Vercel URL and sign in with the default Super Admin (`superadmin@leaders.edu` / `LeadersAdmin!2026`), then **immediately reset all default staff passwords** in Staff Management for production security.
