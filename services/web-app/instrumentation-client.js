// instrumentation-client.js
// This file runs on the CLIENT side only.
// Initializes Datadog RUM + Session Replay + Browser Logs.

import { datadogRum } from '@datadog/browser-rum';
import { nextjsPlugin } from '@datadog/browser-rum-nextjs';
import { datadogLogs } from '@datadog/browser-logs';

const APP_ID = process.env.NEXT_PUBLIC_DD_APP_ID || '94797379-4fae-4278-8cb4-1832fb6f3860';
const CLIENT_TOKEN = process.env.NEXT_PUBLIC_DD_CLIENT_TOKEN || 'pub90993195e58a0783b852841cfc9d1339';
const ENV = process.env.NEXT_PUBLIC_DD_ENV || 'dev';

// ── Initialize RUM ────────────────────────────────────────────────────────
datadogRum.init({
  applicationId: APP_ID,
  clientToken: CLIENT_TOKEN,
  site: 'datadoghq.com',
  service: 'hippogriff-web',
  env: ENV,
  version: '1.0.0',

  // Capture 100% of sessions — good for demo, lower in production
  sessionSampleRate: 100,

  // Capture 100% of sessions with Session Replay
  sessionReplaySampleRate: 100,

  // Track all resource loads (API calls, images, fonts)
  trackResources: true,

  // Track clicks, form inputs, scroll events
  trackUserInteractions: true,

  // Track long tasks (UI freezes > 50ms)
  trackLongTasks: true,

  // Next.js plugin handles route change tracking automatically
  plugins: [nextjsPlugin()],

  // APM-RUM correlation — links frontend sessions to backend traces
  allowedTracingUrls: [
    // Trace requests to the backend services
    // In production, these would be your actual API domain
    /http:\/\/localhost:\d+/,
    /http:\/\/.*\.hippogriff\.internal/,
  ],

  // Privacy settings
  defaultPrivacyLevel: 'mask-user-input',
});

// ── Initialize Browser Logs ───────────────────────────────────────────────
datadogLogs.init({
  clientToken: CLIENT_TOKEN,
  site: 'datadoghq.com',
  service: 'hippogriff-web',
  env: ENV,
  version: '1.0.0',
  forwardErrorsToLogs: true,
  sessionSampleRate: 100,
});

// Export required for Next.js route transition tracking
export { onRouterTransitionStart } from '@datadog/browser-rum-nextjs';
