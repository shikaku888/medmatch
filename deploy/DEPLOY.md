# Deploy MedMatch AI — một container, một URL

Container chạy 2 service: **Express BFF + React build** (công khai, `$PORT` — Cloud Run inject 8080) và **FastAPI engine** (nội bộ 127.0.0.1:8765). Browser/app chỉ cần 1 URL.

## Build & chạy local (cần Docker Desktop đang chạy)

```bash
cd H:\aisuckhoe
docker build -f deploy/Dockerfile -t medmatch-ai .
docker run --rm -p 8080:8080 -e PORT=8080 medmatch-ai
# mở http://localhost:8080
```

## Deploy Cloud Run (cần gcloud CLI + project có billing)

```bash
gcloud run deploy medmatch-ai \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --memory 1Gi --cpu 1 \
  --set-env-vars NODE_ENV=production
```
(`--source .` dùng Cloud Build remote — không cần Docker local. Build pack đọc `deploy/Dockerfile` qua `--source` + `gcloud run deploy` tự nhận Dockerfile ở gốc? KHÔNG — chỉ định: thêm file `cloudbuild.yaml` hoặc dùng `--dockerfile deploy/Dockerfile` (gcloud ≥ 470 hỗ trợ `gcloud run deploy --source . --dockerfile deploy/Dockerfile`).)

## Bên trong image

- `/app/medmatch/backend` + `medmatch.db` (297MB, chứa sẵn 22,680 cặp unified + 7,472 barcode DSLD + review queue)
- `/app/scanner/dist` (React build) + `dist/server.cjs` (Express BFF bundle) + `node_modules`
- `start.sh`: uvicorn (nền) + node (foreground); service nào chết → container chết (Cloud Run tự restart)

## Lưu ý vận hành

1. **Filesystem ephemeral** (Cloud Run): mọi ghi runtime (data_storage.json, lookup_cache.db, review queue, lịch sử) MẤT khi instance scale-down. MVP chấp nhận được; lâu dài gắn Cloud SQL / volume hoặc chuyển storage sang SQLite trên volume.
2. **SQLite + nhiều instance**: Cloud Run scale theo request → nhiều instance = nhiều DB riêng không đồng bộ. MVP: giới hạn `--max-instances 1`.
3. **Tesseract OCR**: lần đầu gọi Photo OCR sẽ tải `eng.traineddata` từ CDN (network egress OK trên Cloud Run).
4. **Secrets**: hiện không cần key nào. Sau này thêm (UPCitemdb…) → `--set-secrets`.
