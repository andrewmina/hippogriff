'use client';

import { useState } from 'react';

type Props = {
  bets: any[];
  userId: string;
  betServiceUrl: string;
};

const SELECTION_LABELS: Record<string, string> = {
  home_win: 'Home Win',
  away_win: 'Away Win',
  draw: 'Draw',
  over: 'Over',
  under: 'Under',
};

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-yellow-900 text-yellow-300',
  won: 'bg-green-900 text-green-300',
  lost: 'bg-red-900 text-red-300',
  void: 'bg-gray-700 text-gray-400',
};

export default function MyBets({ bets, userId, betServiceUrl }: Props) {
  const [expanded, setExpanded] = useState(true);

  if (bets.length === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-bold text-white mb-3">📜 My Bets</h3>
        <div className="text-center py-4 text-gray-500 text-sm">
          <p className="text-2xl mb-2">🎰</p>
          No bets placed yet
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <button
        className="w-full flex items-center justify-between mb-3"
        onClick={() => setExpanded(!expanded)}
      >
        <h3 className="text-sm font-bold text-white">
          📜 My Bets
          <span className="ml-2 bg-purple-700 text-white text-xs px-1.5 py-0.5 rounded-full">
            {bets.length}
          </span>
        </h3>
        <span className="text-gray-400 text-xs">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {bets.map(bet => (
            <div key={bet.bet_id} className="bg-gray-800 rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-400">{bet.event_id?.split('_').slice(0, 3).join(' ')}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded capitalize ${STATUS_STYLES[bet.status] || STATUS_STYLES.pending}`}>
                  {bet.status}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-white">
                    {SELECTION_LABELS[bet.selection] || bet.selection}
                  </p>
                  <p className="text-xs text-gray-400">
                    Stake: <span className="text-white">${parseFloat(bet.stake).toFixed(2)}</span>
                    {' '}@ <span className="text-yellow-400">{parseFloat(bet.odds).toFixed(2)}</span>
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-400">Return</p>
                  <p className="text-sm font-bold text-green-400">
                    ${parseFloat(bet.potential_payout).toFixed(2)}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
