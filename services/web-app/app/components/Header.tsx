'use client';

import { useState } from 'react';
import { datadogRum } from '@datadog/browser-rum';

export default function Header() {
  const [balance] = useState(1000.00);

  return (
    <header className="border-b border-gray-800 bg-gray-950 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <span className="text-2xl">🦅</span>
          <div>
            <h1 className="text-xl font-bold text-white leading-none">Hippogriff</h1>
            <p className="text-xs text-purple-400 leading-none">Real-Time Sports Betting</p>
          </div>
        </div>

        {/* Live indicator */}
        <div className="hidden md:flex items-center gap-2">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
          </span>
          <span className="text-xs text-green-400 font-medium">LIVE ODDS</span>
        </div>

        {/* Balance + user */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-xs text-gray-400">Balance</p>
            <p className="text-sm font-bold text-green-400">${balance.toFixed(2)}</p>
          </div>
          <button
            className="bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            onClick={() => datadogRum.addAction('deposit_clicked', {})}
          >
            Deposit
          </button>
        </div>
      </div>
    </header>
  );
}
