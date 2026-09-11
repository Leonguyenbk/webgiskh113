-- Chẩn đoán CPU cao do get_ranh_gioi_thon — CHỈ ĐỌC, an toàn chạy trên
-- production kể cả khi Supabase đang tải cao (không EXPLAIN ANALYZE trên dữ
-- liệu lớn, không sửa gì). Chạy từng khối, không cần chạy hết 1 lượt.

-- 1) Định nghĩa hàm ĐANG CHẠY THẬT trên Supabase — đối chiếu với
--    supabase/schema.sql trong repo để chắc chắn không bị lệch (vd ai đó
--    từng sửa tay qua SQL Editor mà chưa đồng bộ lại vào repo).
select pg_get_functiondef('public.get_ranh_gioi_thon(text)'::regprocedure);

-- 2) Có phiên nào đang chạy get_ranh_gioi_thon ngay lúc này không, chạy bao
--    lâu rồi, đang chờ gì (lock/IO/CPU).
select
    pid,
    usename,
    state,
    now() - query_start as running_time,
    wait_event_type,
    wait_event,
    left(query, 1000) as query
from pg_stat_activity
where query ilike '%get_ranh_gioi_thon%'
  and pid <> pg_backend_pid()
order by query_start;

-- 3) Thống kê tổng hợp — cần extension pg_stat_statements (Supabase bật sẵn
--    mặc định ở phần lớn dự án; nếu trống, bật ở Database -> Extensions).
--    Trước khi sửa: total_exec_time cao dần theo calls, mean_exec_time cỡ
--    hàng giây/chục giây cho biến thể p_ma_xa=null.
select
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time,
    rows,
    left(query, 2000) as query
from pg_stat_statements
where query ilike '%get_ranh_gioi_thon%'
order by total_exec_time desc
limit 20;

-- =========================================================
-- CHẠY SAU KHI ĐÃ ÁP DỤNG supabase/schema.sql (bản có ranh_gioi_thon_cache)
-- =========================================================

-- 4) Cache đã có đủ dữ liệu cho các xã đang có ranh_gioi_thon chưa (2 số
--    phải bằng nhau).
select
    (select count(distinct ma_xa) from public.ranh_gioi_thon) as so_xa_co_ranh,
    (select count(*) from public.ranh_gioi_thon_cache) as so_xa_da_cache;

-- 5) Đo lại thời gian gọi get_ranh_gioi_thon(null) SAU khi có cache — kỳ
--    vọng dưới 1 giây (so với ~18.7 giây trước khi sửa, đo trên 7 xã/149
--    thôn ngày 2026-09-11). Bọc EXPLAIN ANALYZE vì bảng cache rất nhỏ, an
--    toàn chạy kể cả lúc tải cao.
explain (analyze, buffers, verbose)
select public.get_ranh_gioi_thon(null);

-- 6) Nếu muốn build lại cache tay cho 1 xã cụ thể (vd sau khi sửa dữ liệu
--    ranh_gioi_thon trực tiếp bằng SQL, không qua backend):
-- select public.refresh_ranh_gioi_thon_cache('24373');

-- 7) Sau khi đã áp dụng và chạy vài ngày — so lại pg_stat_statements như
--    bước 3, số calls tương tự nhưng total_exec_time phải giảm mạnh (không
--    còn ST_AsGeoJSON tính trực tiếp trên đường đọc).
