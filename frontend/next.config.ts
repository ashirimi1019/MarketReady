import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactCompiler: true,
  compress: true,
  poweredByHeader: false,
};

export default nextConfig;
