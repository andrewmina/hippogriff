import type { Metadata } from 'next';
import { DatadogAppRouter } from '@datadog/browser-rum-nextjs';
import './globals.css';

export const metadata: Metadata = {
  title: 'Hippogriff — Real-Time Sports Betting',
  description: 'The sharpest odds in the game',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white min-h-screen">
        {/* DatadogAppRouter enables automatic route change tracking */}
        <DatadogAppRouter />
        {children}
      </body>
    </html>
  );
}
