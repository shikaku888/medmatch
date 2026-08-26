@echo off
REM ============================================================
REM MedMatch AI — one-click deploy to Cloud Run (needs gcloud)
REM 1) Install gcloud: https://cloud.google.com/sdk/docs/install
REM 2) Edit PROJECT_ID below
REM 3) Double-click this file
REM ============================================================
setlocal

set PROJECT_ID=YOUR_GCP_PROJECT_ID
set REGION=asia-southeast1
set SERVICE=medmatch-ai
set BUCKET=%PROJECT_ID%-medmatch-db

where gcloud >nul 2>nul
if errorlevel 1 (
  echo [X] gcloud not found. Install: https://cloud.google.com/sdk/docs/install
  exit /b 1
)
if "%PROJECT_ID%"=="YOUR_GCP_PROJECT_ID" (
  echo [X] Edit this file: set PROJECT_ID to your GCP project id first.
  exit /b 1
)

echo == Setting project %PROJECT_ID%
gcloud config set project %PROJECT_ID% || exit /b 1

echo == Enabling APIs (first run only)
gcloud services enable cloudbuild.googleapis.com run.googleapis.com storage.googleapis.com --quiet

echo == Uploading database to GCS (297MB, one-time; re-run to refresh data)
gcloud storage buckets create gs://%BUCKET% --location=%REGION% --quiet 2>nul
gcloud storage cp "H:\aisuckhoe\medmatch\backend\medmatch.db" gs://%BUCKET%/medmatch.db || exit /b 1

echo == Deploying Cloud Run service %SERVICE%
gcloud run deploy %SERVICE% ^
  --source "H:\aisuckhoe" ^
  --dockerfile deploy/Dockerfile ^
  --region %REGION% ^
  --allow-unauthenticated ^
  --memory 1Gi --cpu 1 --max-instances 1 --concurrency 40 ^
  --add-volume name=dbvol,type=cloud-storage,bucket=%BUCKET% ^
  --mount name=dbvol,path=/app/dbvolume ^
  --set-env-vars "MEDMATCH_DB=/app/dbvolume/medmatch.db,NODE_ENV=production" ^
  --quiet || exit /b 1

for /f "delims=" %%U in ('gcloud run services describe %SERVICE% --region %REGION% --format "value(status.url)"') do set URL=%%U
echo.
echo == DONE: %URL%
echo (iOS app sau này gọi chính URL này)
