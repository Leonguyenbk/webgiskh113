import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const allowedHosts = ["kh113.vpdkdaklak.vn", "www.kh2959bmt.net", "kh2959bmt.net"];

// Đo thời gian ĐẦU-CUỐI mỗi lượt nộp biểu Nhóm 4 (từ lúc request tới proxy
// đến lúc trả xong, gồm cả thời gian tải file từ máy người dùng lên) —
// so với "xu_ly_ms" trong backend/logs/nhom4_submit.log để tách phần
// đường truyền với phần máy chủ xử lý. Ghi ra stdout (service-stdout.log).
function logNhom4Submit(proxyServer) {
  // "start" thay vì "proxyReq": proxyReq bị bỏ qua khi request có header
  // Expect (upload lớn từ một số client).
  proxyServer.on("start", (req, res) => {
    if (req.method !== "POST" || !req.url.startsWith("/api/nhom4/ho-so")) return;
    const started = Date.now();
    let aborted = false;
    req.on("aborted", () => {
      aborted = true;
    });
    res.on("close", () => {
      console.log(
        JSON.stringify({
          luc: new Date(started).toLocaleString("sv-SE"),
          ip: req.headers["cf-connecting-ip"] || req.socket.remoteAddress,
          bytes: Number(req.headers["content-length"]) || null,
          tong_ms: Date.now() - started,
          status: res.statusCode,
          bi_huy: aborted || !res.writableFinished,
        }),
      );
    });
  });
}

const proxy = {
  "/api": {
    target: "http://127.0.0.1:5000",
    changeOrigin: true,
    configure: logNhom4Submit,
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
