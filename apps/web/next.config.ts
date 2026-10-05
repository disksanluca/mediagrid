import type { NextConfig } from "next";

const desktop = process.env.MEDIAGRID_DESKTOP_BUILD === "1";

const nextConfig: NextConfig = desktop
  ? {output: "export", images: {unoptimized: true}}
  : {
      async rewrites() {
        return [{source: "/api/v1/:path*", destination: "http://127.0.0.1:8000/api/v1/:path*"}];
      },
    };

export default nextConfig;
