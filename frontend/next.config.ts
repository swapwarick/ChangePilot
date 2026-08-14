import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Required for the production Docker build (standalone server.js output)
  output: "standalone",
};

export default nextConfig;

