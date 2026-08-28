-- =========================================================
-- MIGRATION THỦ CÔNG — gỡ cơ chế khóa phụ của biểu Nhóm 4.
--
-- Chạy 1 lần trong Supabase SQL Editor của project WebGIS hiện tại.
-- KHÔNG chạy tự động ở runtime (backend không đụng tới các đối tượng này
-- nữa kể từ khi flow Nhóm 4 chuyển sang chỉ dựa vào public.du_lieu_gcn).
--
-- Bối cảnh: bảng public.nhom4_thua_da_nop + RPC public.nhom4_claim_keys()
-- từng dùng để "giữ chỗ" nguyên tử cho thửa sắp nộp. Cơ chế này có thể
-- giữ lại khóa cũ khi insert du_lieu_gcn lỗi giữa chừng, khiến một thửa
-- chưa hề có dữ liệu trong du_lieu_gcn vẫn bị báo "đã nộp trùng". Nay bỏ
-- hoàn toàn: du_lieu_gcn là nguồn duy nhất xác định thửa đã có dữ liệu.
--
-- An toàn chạy lại nhiều lần (IF EXISTS). Không ảnh hưởng du_lieu_gcn hay
-- bất kỳ bảng/RPC WebGIS nào khác.
-- =========================================================

DROP FUNCTION IF EXISTS public.nhom4_claim_keys(text[]);
DROP TABLE IF EXISTS public.nhom4_thua_da_nop;
