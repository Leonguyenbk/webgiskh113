# Triển khai React lên Vercel và Flask lên Render

## Kiến trúc

```text
Người dùng
  → React/Vercel (HTTPS, GPS)
  → Flask/Render (HTTPS, API)
  → Supabase PostGIS
```

## 1. Đưa project lên GitHub

Tạo một repository trống trên GitHub, ví dụ `webgis-thua-dat`, không tạo sẵn
README hoặc `.gitignore`.

Chạy trong PowerShell tại thư mục project:

```powershell
git init
git add .
git commit -m "WebGIS deploy Vercel Render"
git branch -M main
git remote add origin https://github.com/USERNAME/webgis-thua-dat.git
git push -u origin main
```

Thay `USERNAME` bằng tài khoản GitHub. File `backend/.env` đã được `.gitignore`
loại trừ và không được đưa lên GitHub.

## 2. Deploy Flask lên Render trước

1. Vào Render Dashboard.
2. Chọn **New → Web Service**.
3. Kết nối repository GitHub vừa tạo.
4. Điền:

```text
Name: webgis-thua-dat-api
Root Directory: backend
Language: Python 3
Build Command: pip install -r requirements.txt
Start Command: gunicorn run:app --timeout 300 --workers 1 --threads 8 --worker-class gthread
Health Check Path: /api/health
```

5. Trong **Environment Variables**, thêm:

```text
SUPABASE_URL=https://PROJECT_ID.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
FRONTEND_URL=*
```

6. Bấm **Create Web Service**.
7. Khi deploy xong, mở:

```text
https://TEN-DICH-VU.onrender.com/api/health
```

Phải nhận JSON có `"ok": true`. Sao chép URL Render để dùng ở bước tiếp theo.

## 3. Deploy React lên Vercel

1. Vào Vercel Dashboard.
2. Chọn **Add New → Project** và import cùng repository GitHub.
3. Đặt:

```text
Framework Preset: Vite
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
```

4. Thêm Environment Variable:

```text
VITE_API_URL=https://TEN-DICH-VU.onrender.com
```

Không thêm Supabase secret key vào Vercel.

5. Bấm **Deploy**.
6. Mở URL HTTPS mà Vercel cung cấp.

## 4. Giới hạn CORS sau khi có URL Vercel

Quay lại Render → service backend → **Environment**, đổi:

```text
FRONTEND_URL=*
```

thành URL Vercel thật:

```text
FRONTEND_URL=https://TEN-WEB.vercel.app
```

Chọn **Save and deploy**.

Nếu dùng cả tên miền riêng và URL Vercel, phân cách bằng dấu phẩy:

```text
FRONTEND_URL=https://TEN-WEB.vercel.app,https://bando.tenmien.vn
```

## 5. Kiểm tra

1. Bản đồ hiển thị nền vệ tinh (Google).
2. Hiển thị đủ dữ liệu thửa từ Supabase.
3. Bấm một thửa để xem thuộc tính.
4. Màu thửa thay đổi theo loại đất.
5. Bấm **Vị trí của tôi** và cho phép quyền GPS.

Gói Render miễn phí có thể ngủ sau một thời gian không sử dụng, nên lần mở đầu
tiên đôi khi phải đợi backend khởi động.

## 6. Đồng bộ dữ liệu GCN từ web (nút "Đồng bộ" + tự động mỗi 30 phút)

Trang **Công cụ → Nhập đường link** có nút "Đồng bộ" đọc lại Google Sheet và
ghi vào Supabase ngay trên backend Render (không cần chạy `sync_gcn/main.py`
thủ công nữa). Cần cấu hình thêm:

### 6.1. Trên Render (service backend)

Vào **Environment**, thêm 2 biến:

```text
IMPORT_TOKEN=<một chuỗi bí mật tự đặt>
GOOGLE_SERVICE_ACCOUNT_JSON=<nguyên văn nội dung file service_account.json>
```

- `IMPORT_TOKEN`: cùng một token dùng để xác thực các thao tác ghi dữ liệu
  (import GML, nhập link, đồng bộ...). Nếu để trống, các endpoint này KHÔNG
  yêu cầu xác thực — nên luôn đặt token khi đã có nút Đồng bộ công khai.
- `GOOGLE_SERVICE_ACCOUNT_JSON`: mở file `service_account.json` (file đã tạo
  theo hướng dẫn ở `sync_gcn/README.md`, mục 3) bằng Notepad, copy toàn bộ
  nội dung (đúng 1 dòng JSON, không xuống dòng), dán vào ô Value trên Render.
  File này chỉ dùng cục bộ trước đây (bị `.gitignore` loại trừ) — dán vào
  Render không đưa lên GitHub.

Sau khi lưu, Render tự redeploy. Mở lại trang **Nhập đường link**, nhập mã
xác thực (đúng `IMPORT_TOKEN`) vào ô "Mã xác thực" rồi bấm **Đồng bộ** ở một
nguồn để kiểm tra.

### 6.2. Trên GitHub (tự động đồng bộ mỗi 30 phút)

Workflow `.github/workflows/sync-gcn.yml` tự gọi API đồng bộ tất cả nguồn
đang kích hoạt mỗi 30 phút. Vào **Settings → Secrets and variables →
Actions → New repository secret**, thêm:

```text
BACKEND_URL=https://TEN-DICH-VU.onrender.com
IMPORT_TOKEN=<giống hệt IMPORT_TOKEN đã đặt trên Render>
```

Có thể bấm **Actions → Đồng bộ dữ liệu GCN → Run workflow** để chạy thử ngay
thay vì đợi lịch 30 phút.
