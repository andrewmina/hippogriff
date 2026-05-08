/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  env: {
    NEXT_PUBLIC_ODDS_ENGINE_URL: process.env.NEXT_PUBLIC_ODDS_ENGINE_URL || 'http://localhost:8001',
    NEXT_PUBLIC_BET_SERVICE_URL: process.env.NEXT_PUBLIC_BET_SERVICE_URL || 'http://localhost:8002',
    NEXT_PUBLIC_TIP_SERVICE_URL: process.env.NEXT_PUBLIC_TIP_SERVICE_URL || 'http://localhost:8003',
    NEXT_PUBLIC_DD_APP_ID: process.env.NEXT_PUBLIC_DD_APP_ID || '',
    NEXT_PUBLIC_DD_CLIENT_TOKEN: process.env.NEXT_PUBLIC_DD_CLIENT_TOKEN || '',
    NEXT_PUBLIC_DD_ENV: process.env.NEXT_PUBLIC_DD_ENV || 'dev',
  },
};

module.exports = nextConfig;
