import type { NextConfig } from "next";

const desktop = process.env.MEDIAGRID_DESKTOP_BUILD === "1";
const apiPort = process.env.MEDIAGRID_API_PORT ?? "8000";
if (!/^\d+$/.test(apiPort) || Number(apiPort) < 1 || Number(apiPort) > 65535) {
  throw new Error("MEDIAGRID_API_PORT must be a TCP port");
}

const nextConfig: NextConfig = desktop
  ? {agentRules: false, output: "export", images: {unoptimized: true}}
  : {
      agentRules: false,
      async rewrites() {
        return [{source: "/api/v1/:path*", destination: `http://127.0.0.1:${apiPort}/api/v1/:path*`}];
      },
    };

export default nextConfig;
