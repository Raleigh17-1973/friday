/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,

  // Enable standalone output for Docker / self-hosted deployments.
  // Vercel handles this automatically — standalone is a no-op on Vercel.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,

  // Server-side env vars forwarded to Next.js API routes.
  // FRIDAY_BACKEND_URL is intentionally server-only (not NEXT_PUBLIC_) to avoid
  // exposing the internal backend URL to the browser.
  serverRuntimeConfig: {
    backendUrl: process.env.FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000",
  },
};

export default nextConfig;
