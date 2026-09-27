import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// The browser calls /api/* on the same address as the page; Next.js forwards it to FastAPI.
// This works from phones on the same Wi-Fi (no 127.0.0.1 problem) and needs no CORS.
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Lets a production build go to a separate folder (e.g. to measure page size while `next dev` runs).
  distDir: process.env.NEXT_DIST_DIR || ".next",
  output: "standalone", // small self-contained server for Docker
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
      { source: "/health", destination: `${BACKEND_URL}/health` },
    ];
  },
};

export default withNextIntl(nextConfig);
