'use client';

import { useEffect } from 'react';
import { addNextjsError } from '@datadog/browser-rum-nextjs';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Report error to Datadog RUM Error Tracking
    addNextjsError(error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="card max-w-md w-full text-center">
        <div className="text-4xl mb-4">⚠️</div>
        <h2 className="text-xl font-bold text-red-400 mb-2">Something went wrong</h2>
        <p className="text-gray-400 text-sm mb-4">{error.message}</p>
        <button
          onClick={reset}
          className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-2 rounded-lg"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
