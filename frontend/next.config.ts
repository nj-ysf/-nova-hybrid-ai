import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Django REST Framework uses trailing-slash routes. Next requires the slash
  // in both rewrite patterns when proxying to a backend that expects it.
  trailingSlash: true,
  async rewrites() {
    const djangoApiUrl = process.env.DJANGO_API_URL;

    if (!djangoApiUrl) return [];

    return [
      {
        source: "/static/:path*",
        destination: `${djangoApiUrl.replace(/\/$/, "")}/static/:path*`,
      },
      {
        source: "/api/:path*/",
        destination: `${djangoApiUrl.replace(/\/$/, "")}/api/:path*/`,
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
