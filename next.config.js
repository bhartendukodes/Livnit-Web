/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  
  // Image optimization configuration
  images: {
    unoptimized: false,
    remotePatterns: [],
    formats: ['image/avif', 'image/webp'],
  },
  
  // Webpack configuration for Three.js and model-viewer
  webpack: (config, { isServer }) => {
    // Fix for Three.js and model-viewer
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        crypto: false,
      }
    }
    
    // Handle model-viewer and Three.js properly
    config.externals = config.externals || []
    
    return config
  },
  
  // Allow access to backend API
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL || 'https://pipeline.livinit.ai'}/:path*`,
      },
    ]
  },
  
  // Configure headers for development
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Access-Control-Allow-Origin',
            value: '*',
          },
          {
            key: 'Access-Control-Allow-Methods',
            value: 'GET, POST, PUT, DELETE, OPTIONS',
          },
          {
            key: 'Access-Control-Allow-Headers',
            value: 'Content-Type, Authorization',
          },
        ],
      },
    ]
  },
  
  // Output configuration
  output: 'standalone',
  
  // Experimental features
  experimental: {
    optimizePackageImports: ['three', '@google/model-viewer'],
  },
}

module.exports = nextConfig