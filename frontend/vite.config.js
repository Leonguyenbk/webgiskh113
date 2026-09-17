import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // Cloudflare Tunnel chuyển tiếp request với Host header là tên miền
    // công khai — Vite dev server mặc định chặn Host lạ (chống DNS
    // rebinding) nên phải khai báo rõ tên miền tunnel ở đây.
    allowedHosts: ["kh113.vpdkdaklak.vn", "www.kh2959bmt.net", "kh2959bmt.net"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/tiles": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
    },
  },
});
