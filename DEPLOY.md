# Triển khai React lên Vercel và Flask lên Render

## Kiến trúc

```text
Người dùng
  → React/Vercel (HTTPS, GPS)
  → Flask/Render (HTTPS, API + proxy Vietbando)
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
Start Command: gunicorn app:app
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

1. Bản đồ hiển thị nền Vietbando.
2. Hiển thị đủ dữ liệu thửa từ Supabase.
3. Bấm một thửa để xem thuộc tính.
4. Màu thửa thay đổi theo loại đất.
5. Bấm **Vị trí của tôi** và cho phép quyền GPS.

Gói Render miễn phí có thể ngủ sau một thời gian không sử dụng, nên lần mở đầu
tiên đôi khi phải đợi backend khởi động.
