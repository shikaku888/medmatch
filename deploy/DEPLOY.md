# Deploy MedMatch AI — một container, một URL

**Đường chính (Windows, không cần Docker):**
1. Cài gcloud CLI: https://cloud.google.com/sdk/docs/install
2. `gcloud init` + tạo project có billing
3. Sửa `deploy\deploy.cmd` → điền `PROJECT_ID`
4. Chạy `deploy\deploy.cmd` — tự: bật API, upload cơ sở dữ liệu hợp nhất lên GCS bucket, deploy Cloud Run với GCS FUSE volume (`MEDMATCH_DB=/app/dbvolume/medmatch.db`), in URL.

> DB KHÔNG đi theo source upload (Cloud Build giới hạn ~100MB nén) — nó nằm trong GCS bucket, mount read-write vào container qua volume. Cập nhật dữ liệu = chạy lại `gcloud storage cp` + restart service.

---

**Đường phụ (có Docker Desktop):**

```bash
cd G:\aisuckhoe
docker build -f deploy/Dockerfile -t medmatch-ai .
docker run --rm -p 8080:8080 -e PORT=8080 medmatch-ai
# mở http://localhost:8080
```
(DB bake sẵn trong image ở đường này — MEDMATCH_DB không set, dùng file mặc định.)

## Bên trong image

- `/app/medmatch/backend` + mã lõi; **cơ sở dữ liệu mount từ GCS volume** tại `/app/dbvolume/medmatch.db` (Cloud Run) hoặc dùng bản cục bộ khi chạy Docker — chứa dữ liệu interaction và product index đã hợp nhất
- `/app/medmatch/static` + giao diện React scanner; FastAPI phục vụ cùng một địa chỉ
- `start.sh`: uvicorn foreground trên `$PORT`; service duy nhất chết thì Cloud Run restart container
## Lưu ý vận hành

1. **DB ghi được và bền** nhờ GCS FUSE volume (không ephemeral như mặc định Cloud Run). GCS FUSE không phải block storage — ghi đồng thời nhiều instance vẫn nguy hiểm → giữ `--max-instances 1` cho MVP.
2. **Cập nhật dữ liệu**: chạy lại import trên máy → `gcloud storage cp medmatch/backend/medmatch.db gs://BUCKET/medmatch.db` → restart service.
3. **Tesseract OCR**: lần đầu gọi Photo OCR sẽ tải `eng.traineddata` từ CDN (egress OK trên Cloud Run).
4. **Secrets**: hiện không cần key nào. Sau này thêm (UPCitemdb…) → `--set-secrets`.
