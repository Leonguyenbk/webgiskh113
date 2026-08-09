# sync_gcn

Đồng bộ dữ liệu GCN từ Google Sheet vào bảng `public.du_lieu_gcn` trên
Supabase (project WebGIS hiện có — không tạo project mới, không đụng
tới `thua_dat`/`dong_bo_du_lieu` hay bảng WebGIS nào khác).

## 1. Tạo bảng trên Supabase

Mở **Supabase SQL Editor** của project WebGIS hiện tại, chạy nguyên văn
file `create_du_lieu_gcn.sql`. Chỉ tạo bảng mới `du_lieu_gcn`, an toàn
chạy lại nhiều lần (`create table if not exists`, `create index if not
exists`).

## 2. Cài đặt trên Windows

```powershell
cd sync_gcn
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Google Service Account

1. Vào Google Cloud Console → tạo (hoặc dùng lại) một Service Account,
   bật **Google Sheets API** và **Google Drive API**.
2. Tạo key dạng JSON, tải về, đổi tên thành `service_account.json` và
   đặt trong thư mục `sync_gcn/` (đã có sẵn trong `.gitignore`, không
   bị commit lên git).
3. Mở từng Google Sheet cần đồng bộ → **Share** → thêm email của
   Service Account (dạng `...@...iam.gserviceaccount.com`, xem trong
   file JSON) với quyền **Viewer**.

## 4. Cấu hình `.env`

```powershell
copy .env.example .env
```

Sửa `sync_gcn\.env`:

```env
SUPABASE_URL=https://xxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...           # Service Role Key, KHÔNG phải anon key
GOOGLE_CREDENTIALS_FILE=service_account.json
```

`SUPABASE_URL`/`SUPABASE_SERVICE_KEY` lấy ở Supabase Dashboard → Project
Settings → API (mục "service_role"). File `.env` đã có trong
`.gitignore`, không commit lên git.

## 5. Khai báo danh sách Google Sheet

File `danh_sach_sheet.xlsx` (đã có sẵn dữ liệu mẫu) gồm 4 cột:

| ma_nguon | ten_nguon | url                                    | kich_hoat |
|----------|-----------|-----------------------------------------|-----------|
| 001      | Nguon 1   | https://docs.google.com/spreadsheets/... | 1         |
| 002      | Nguon 2   | https://docs.google.com/spreadsheets/... | 0         |

- `ma_nguon`: mã định danh nguồn, **phải duy nhất** (chương trình sẽ
  dừng nếu trùng).
- `url`: link Google Sheet đầy đủ (đã share Viewer cho service account).
- `kich_hoat`: `1` mới được đồng bộ, mọi giá trị khác bị bỏ qua.

Muốn thêm nguồn mới: chỉ cần thêm một dòng vào file Excel này, không
cần sửa code Python. Mỗi Google Sheet phải có worksheet tên đúng
`Trang tính1`, dữ liệu 56 cột theo đúng thứ tự đã map trong
`config.py`, bắt đầu từ ô `B3`.

## 6. Chạy đồng bộ

```powershell
venv\Scripts\activate
python main.py
```

Kết quả in ra dạng:

```text
[001] Nguon 1: OK - 18.520 dòng
[002] Nguon 2: ERROR - WorksheetNotFound

===== Tổng kết =====
Tổng nguồn  : 2
Thành công  : 1
Lỗi         : 1
Tổng bản ghi: 18.520
Nguồn lỗi:
  - [002] Nguon 2: WorksheetNotFound: ...
```

Một nguồn lỗi không ảnh hưởng các nguồn khác. Với mỗi nguồn, chương
trình luôn đọc + kiểm tra toàn bộ Google Sheet xong xuôi trước, chỉ sau
đó mới xóa dữ liệu cũ của `ma_nguon` đó trên Supabase và insert lại
theo batch 500 dòng — nếu đọc Sheet lỗi thì dữ liệu cũ trên Supabase
giữ nguyên, không bị đụng tới.

## 7. Chạy định kỳ (tuỳ chọn)

Có thể lên lịch bằng Windows Task Scheduler, gọi:

```text
D:\...\sync_gcn\venv\Scripts\python.exe D:\...\sync_gcn\main.py
```

## Giới hạn phiên bản đầu

Việc "xóa dữ liệu cũ của một nguồn rồi insert lại" không phải một
transaction thật sự ở tầng Supabase — nếu mất kết nối giữa lúc đang
insert (sau khi đã xóa), nguồn đó có thể tạm thời thiếu dữ liệu. Lần
chạy kế tiếp cho nguồn đó sẽ tự xóa sạch và ghi lại từ đầu nên tự sửa,
nhưng không ảnh hưởng các nguồn khác. Muốn tuyệt đối an toàn hơn có thể
chuyển sang một hàm RPC (`plpgsql`) làm DELETE+INSERT trong cùng một
transaction ở phiên bản sau.
