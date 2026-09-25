import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const djangoApiUrl = process.env.DJANGO_API_URL;

    if (!djangoApiUrl) return [];

    return [
      {
        source: "/api/:path*",
        destination: `${djangoApiUrl.replace(/\/$/, "")}/api/:path*`,
      },
      {
        source: "/login/",
        destination: `${djangoApiUrl.replace(/\/$/, "")}/login/`,
      },
      {
        source: "/logout/",
        destination: `${djangoApiUrl.replace(/\/$/, "")}/logout/`,
      },
    ];
  },
};

export default nextConfig;
