import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:5050",
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq) => {
            proxyReq.setTimeout(0);
          });
          proxy.on("proxyRes", (_proxyRes, req) => {
            req.socket?.setTimeout(0);
          });
        },
      },
    },
  },
});
