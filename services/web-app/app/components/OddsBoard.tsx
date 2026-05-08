'use client';

import { datadogRum } from '@datadog/browser-rum';
import type { Event, OddsData, Bet } from '../page';

type Props = {
  events: Event[];
  oddsMap: Record<string, OddsData>;
  selectedBet: Bet | null;
  onSelectBet: (bet: Bet) => void;
};

const SPORT_ICONS: Record<string, string> = {
  football: '🏈',
  soccer: '⚽',
  basketball: '🏀',
  baseball: '⚾',
  hockey: '🏒',
};

function formatOdds(odds: number): string {
  if (!odds) return '-';
  return odds.toFixed(2);
}

function isSelected(selectedBet: Bet | null, eventId: string, selection: string): boolean {
  return selectedBet?.eventId === eventId && selectedBet?.selection === selection;
}

export default function OddsBoard({ events, oddsMap, selectedBet, onSelectBet }: Props) {
  const handleOddsClick = (event: Event, selection: string, odds: number, marketStatus: string) => {
    if (marketStatus === 'suspended') {
      datadogRum.addAction('odds_click_suspended', { event_id: event.event_id });
      return;
    }

    onSelectBet({
      eventId: event.event_id,
      homeTeam: event.home_team,
      awayTeam: event.away_team,
      sport: event.sport,
      selection,
      odds,
      stake: 0,
    });
  };

  if (events.length === 0) {
    return (
      <div className="card text-center py-8 text-gray-400">
        No events for this sport
      </div>
    );
  }

  // Group events by sport
  const grouped = events.reduce((acc, event) => {
    if (!acc[event.sport]) acc[event.sport] = [];
    acc[event.sport].push(event);
    return acc;
  }, {} as Record<string, Event[]>);

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([sport, sportEvents]) => (
        <div key={sport}>
          {/* Sport header */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">{SPORT_ICONS[sport] || '🏆'}</span>
            <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider capitalize">
              {sport}
            </h2>
            <div className="flex-1 h-px bg-gray-800" />
          </div>

          {/* Events */}
          <div className="space-y-2">
            {sportEvents.map(event => {
              const odds = oddsMap[event.event_id];
              const suspended = odds?.market_status === 'suspended';

              return (
                <div
                  key={event.event_id}
                  className={`card transition-all ${suspended ? 'opacity-60' : 'hover:border-gray-700'}`}
                >
                  {/* Event header */}
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-sm font-semibold text-white">
                        {event.home_team} vs {event.away_team}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {new Date(event.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                    <span className={suspended ? 'badge-suspended' : 'badge-live'}>
                      {suspended ? 'SUSPENDED' : 'LIVE'}
                    </span>
                  </div>

                  {/* Odds buttons */}
                  {odds ? (
                    <div className={`grid gap-2 ${odds.draw ? 'grid-cols-3' : 'grid-cols-2'}`}>
                      {/* Home Win */}
                      <button
                        className={`odds-btn text-center ${isSelected(selectedBet, event.event_id, 'home_win') ? 'selected' : ''}`}
                        onClick={() => handleOddsClick(event, 'home_win', odds.home_win, odds.market_status)}
                        disabled={suspended}
                      >
                        <p className="text-xs text-gray-400 mb-1 truncate">{event.home_team}</p>
                        <p className="text-lg font-bold text-yellow-400">{formatOdds(odds.home_win)}</p>
                      </button>

                      {/* Draw (soccer/football only) */}
                      {odds.draw && (
                        <button
                          className={`odds-btn text-center ${isSelected(selectedBet, event.event_id, 'draw') ? 'selected' : ''}`}
                          onClick={() => handleOddsClick(event, 'draw', odds.draw!, odds.market_status)}
                          disabled={suspended}
                        >
                          <p className="text-xs text-gray-400 mb-1">Draw</p>
                          <p className="text-lg font-bold text-yellow-400">{formatOdds(odds.draw)}</p>
                        </button>
                      )}

                      {/* Away Win */}
                      <button
                        className={`odds-btn text-center ${isSelected(selectedBet, event.event_id, 'away_win') ? 'selected' : ''}`}
                        onClick={() => handleOddsClick(event, 'away_win', odds.away_win, odds.market_status)}
                        disabled={suspended}
                      >
                        <p className="text-xs text-gray-400 mb-1 truncate">{event.away_team}</p>
                        <p className="text-lg font-bold text-yellow-400">{formatOdds(odds.away_win)}</p>
                      </button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      {[0, 1].map(i => (
                        <div key={i} className="odds-btn animate-pulse bg-gray-800 h-14" />
                      ))}
                    </div>
                  )}

                  {/* Over/Under row */}
                  {odds && !suspended && (
                    <div className="flex gap-2 mt-2">
                      <button
                        className={`odds-btn flex-1 text-center text-sm ${isSelected(selectedBet, event.event_id, 'over') ? 'selected' : ''}`}
                        onClick={() => handleOddsClick(event, 'over', odds.over_under, odds.market_status)}
                      >
                        <span className="text-gray-400 text-xs">Over </span>
                        <span className="font-bold text-yellow-400">{formatOdds(odds.over_under)}</span>
                      </button>
                      <button
                        className={`odds-btn flex-1 text-center text-sm ${isSelected(selectedBet, event.event_id, 'under') ? 'selected' : ''}`}
                        onClick={() => handleOddsClick(event, 'under', odds.over_under, odds.market_status)}
                      >
                        <span className="text-gray-400 text-xs">Under </span>
                        <span className="font-bold text-yellow-400">{formatOdds(odds.over_under)}</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
