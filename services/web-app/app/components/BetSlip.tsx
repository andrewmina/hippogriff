'use client';

import { useState } from 'react';
import { datadogRum } from '@datadog/browser-rum';
import type { Bet } from '../page';

type Props = {
  selectedBet: Bet | null;
  onPlaceBet: (stake: number) => Promise<void>;
  onClear: () => void;
};

const QUICK_STAKES = [10, 25, 50, 100];

const SELECTION_LABELS: Record<string, string> = {
  home_win: 'Home Win',
  away_win: 'Away Win',
  draw: 'Draw',
  over: 'Over',
  under: 'Under',
};

export default function BetSlip({ selectedBet, onPlaceBet, onClear }: Props) {
  const [stake, setStake] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const stakeNum = parseFloat(stake) || 0;
  const potentialPayout = selectedBet ? (stakeNum * selectedBet.odds).toFixed(2) : '0.00';
  const profit = selectedBet ? ((stakeNum * selectedBet.odds) - stakeNum).toFixed(2) : '0.00';

  const handlePlaceBet = async () => {
    if (!selectedBet || stakeNum <= 0) return;
    setLoading(true);
    setError(null);

    try {
      await onPlaceBet(stakeNum);
      setSuccess(true);
      setStake('');
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || 'Bet placement failed');
      datadogRum.addError(new Error(err.message), { component: 'BetSlip' });
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="card text-center py-6">
        <div className="text-4xl mb-2">✅</div>
        <p className="text-green-400 font-bold">Bet Placed!</p>
        <p className="text-gray-400 text-sm mt-1">Check My Bets for details</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
        🎯 Bet Slip
        {selectedBet && (
          <button onClick={onClear} className="ml-auto text-gray-500 hover:text-red-400 text-xs">
            ✕ Clear
          </button>
        )}
      </h3>

      {!selectedBet ? (
        <div className="text-center py-6 text-gray-500 text-sm">
          <p className="text-2xl mb-2">📋</p>
          Select odds to add a bet
        </div>
      ) : (
        <div className="space-y-3">
          {/* Selected bet */}
          <div className="bg-gray-800 rounded-lg p-3">
            <p className="text-xs text-gray-400 capitalize">{selectedBet.sport}</p>
            <p className="text-sm font-semibold text-white mt-0.5">
              {selectedBet.homeTeam} vs {selectedBet.awayTeam}
            </p>
            <div className="flex items-center justify-between mt-2">
              <span className="text-xs bg-purple-900 text-purple-300 px-2 py-0.5 rounded">
                {SELECTION_LABELS[selectedBet.selection] || selectedBet.selection}
              </span>
              <span className="text-yellow-400 font-bold text-lg">
                {selectedBet.odds.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Quick stake buttons */}
          <div>
            <p className="text-xs text-gray-400 mb-2">Quick stake</p>
            <div className="grid grid-cols-4 gap-1">
              {QUICK_STAKES.map(s => (
                <button
                  key={s}
                  className={`text-xs py-1.5 rounded border transition-colors ${
                    stakeNum === s
                      ? 'border-purple-500 bg-purple-900 text-white'
                      : 'border-gray-700 bg-gray-800 text-gray-300 hover:border-gray-500'
                  }`}
                  onClick={() => {
                    setStake(String(s));
                    datadogRum.addAction('quick_stake_clicked', { stake: s });
                  }}
                >
                  ${s}
                </button>
              ))}
            </div>
          </div>

          {/* Stake input */}
          <div>
            <p className="text-xs text-gray-400 mb-1">Stake amount</p>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
              <input
                type="number"
                min="1"
                max="100000"
                value={stake}
                onChange={e => setStake(e.target.value)}
                placeholder="0.00"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-7 pr-4 py-2
                           text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          {/* Payout info */}
          {stakeNum > 0 && (
            <div className="bg-gray-800 rounded-lg p-3 space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Stake</span>
                <span className="text-white">${stakeNum.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Potential profit</span>
                <span className="text-green-400">+${profit}</span>
              </div>
              <div className="flex justify-between text-sm font-bold border-t border-gray-700 pt-1 mt-1">
                <span className="text-gray-300">Total return</span>
                <span className="text-yellow-400">${potentialPayout}</span>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-900/50 border border-red-700 rounded-lg p-2 text-xs text-red-300">
              {error}
            </div>
          )}

          {/* Place bet button */}
          <button
            className={`w-full py-3 rounded-lg font-bold text-white transition-all ${
              loading || stakeNum <= 0
                ? 'bg-gray-700 cursor-not-allowed'
                : 'bg-purple-600 hover:bg-purple-500 active:scale-98'
            }`}
            onClick={handlePlaceBet}
            disabled={loading || stakeNum <= 0}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                Placing bet...
              </span>
            ) : `Place Bet — $${stakeNum > 0 ? stakeNum.toFixed(2) : '0.00'}`}
          </button>

          <p className="text-xs text-gray-500 text-center">
            Must be 18+. Gamble responsibly.
          </p>
        </div>
      )}
    </div>
  );
}
