/** @type {import('next').NextConfig} */
const apiBaseUrl = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1"
).replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${apiBaseUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
