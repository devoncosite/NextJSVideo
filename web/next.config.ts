import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.STUDIO_BACKEND_URL || "http://127.0.0.1:8008"}/api/:path*`,
      },
      {
        source: "/ws/:path*",
        destination: `${process.env.STUDIO_WS_URL || "http://127.0.0.1:8008"}/ws/:path*`,
      },
    ];
  },
};

export default nextConfig;
