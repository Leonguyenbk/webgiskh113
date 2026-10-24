import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const allowedHosts = ["kh113.vpdkdaklak.vn", "www.kh2959bmt.net", "kh2959bmt.net"];
const proxy = {
  "/api": {
    target: "http://127.0.0.1:5000",
    changeOrigin: true,
  },
  "/tiles": {
    target: "http://127.0.0.1:5000",
    changeOrigin: true,
  },
  // Lớp "Bản đồ đăng ký": Tool Windows đặt URL server có tiền tố này (vừa
  // upload/register, vừa tile_url) — xem backend ban_do_nen_service.py.
  "/ban-do-dang-ky": {
    target: "http://127.0.0.1:5000",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // Cloudflare Tunnel chuyển tiếp request với Host header là tên miền
    // công khai — Vite dev server mặc định chặn Host lạ (chống DNS
    // rebinding) nên phải khai báo rõ tên miền tunnel ở đây.
    allowedHosts,
    proxy,
  },
  // Site thật (WebGIS-Frontend service) chạy `vite preview` đọc khối này,
  // KHÔNG chạy `vite` (dev) nữa — dev server qua Cloudflare Tunnel hay rớt
  // WebSocket HMR, và client Vite hễ phát hiện mất kết nối rồi nối lại là
  // tự ép window.location.reload() toàn trang (hành vi cứng trong
  // @vite/client, không có cách tắt qua config server.hmr), khiến người
  // dùng đang gõ dở biểu Nhóm 4 mất hết dữ liệu chưa submit (lỗi "trang tự
  // reload khi đang nhập" người dùng báo). preview chỉ phục vụ file tĩnh
  // từ dist/ (không có client HMR) nên không còn nguyên nhân reload này —
  // khớp đúng quy trình deploy sẵn có: `npm run build` rồi restart service
  // sau mỗi lần sửa code.
  preview: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts,
    proxy,
  },
});
