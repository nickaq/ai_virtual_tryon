import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {},
  serverExternalPackages: ['winston'],
  webpack: (config) => {
    config.watchOptions = {
      ...config.watchOptions,
      ignored: ['**/ai-service/**', '**/node_modules/**'],
    };
    return config;
  },
  async rewrites() {
    const aiServiceUrl = process.env.AI_SERVICE_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/products/:path*',
        destination: `${aiServiceUrl}/api/products/:path*`,
      },
      {
        source: '/api/orders/:path*',
        destination: `${aiServiceUrl}/api/orders/:path*`,
      },
      {
        source: '/api/orders',
        destination: `${aiServiceUrl}/api/orders`,
      },
      {
        source: '/api/try-on/:path*',
        destination: `${aiServiceUrl}/api/try-on/:path*`,
      },
      {
        source: '/api/uploads/:path*',
        destination: `${aiServiceUrl}/api/uploads/:path*`,
      },
      {
        source: '/api/uploads',
        destination: `${aiServiceUrl}/api/uploads`,
      },
      {
        source: '/api/tryon/:path*',
        destination: `${aiServiceUrl}/api/tryon/:path*`,
      },
      {
        source: '/results/:path*',
        destination: `${aiServiceUrl}/results/:path*`,
      },
      {
        source: '/uploads/:path*',
        destination: `${aiServiceUrl}/uploads/:path*`,
      },
    ];
  },
};

export default nextConfig;
