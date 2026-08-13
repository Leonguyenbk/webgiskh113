// Địa chỉ backend Flask. Giữ nguyên tên biến VITE_API_URL (không đổi thành
// VITE_API_BASE_URL) vì đây là tên đã cấu hình sẵn trên Vercel — đổi tên sẽ
// làm frontend production gọi sai địa chỉ backend cho tới khi ai đó cập
// nhật lại biến môi trường trên Vercel.
export const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
