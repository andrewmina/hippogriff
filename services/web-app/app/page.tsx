'use client';

import { useState, useEffect, useCallback } from 'react';
import { datadogRum } from '@datadog/browser-rum';
import OddsBoard from './components/OddsBoard';
import BetSlip from './components/BetSlip';
import MyBets from './components/MyBets';
import Header from './components/Header';

export type Bet = {
  eventId: string;
  homeTeam: string;
  awayTeam: string;
  sport: string;
  selection: string;
  odds: number;
  stake: number;
};

export type Event = {
  event_id: string;
  sport: string;
  home_team: string;
  away_team: string;
  start_time: string;
};

export type OddsData = {
  event_id: string;
  home_win: number;
  draw?: number;
  away_win: number;
  over_under: number;
  market_status: string;
  timestamp: string;
};

// Generate a persistent user ID for this browser session
function getUserId(): string {
  if (typeof window === 'undefined') return 'server';
  let uid = sessionStorage.getItem('hippogriff_user_id');
  if (!uid) {
    uid = `user-${Math.random().toString(36).substr(2, 9)}`;
    sessionStorage.setItem('hippogriff_user_id', uid);
    // Identify user in Datadog RUM — enables user-level session tracking
    datadogRum.setUser({ id: uid });
  }
  return uid;
}

const ODDS_URL = process.env.NEXT_PUBLIC_ODDS_ENGINE_URL || 'http://localhost:8001';
const BET_URL = process.env.NEXT_PUBLIC_BET_SERVICE_URL || 'http://localhost:8002';

export default function HomePage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [oddsMap, setOddsMap] = useState<Record<string, OddsData>>({});
  const [selectedBet, setSelectedBet] = useState<Bet | null>(null);
  const [placedBets, setPlacedBets] = useState<any[]>([]);
  const [activeSport, setActiveSport] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'odds' | 'mybets'>('odds');
  const userId = typeof window !== 'undefined' ? getUserId() : '';

  const SPORTS = ['all', 'football', 'soccer', 'basketball', 'baseball', 'hockey'];

  // Fetch all events
  const fetchEvents = useCallback(async () => {
    try {
      const res = await fetch(`${ODDS_URL}/events`);
      if (!res.ok) throw new Error('Failed to fetch events');
      const data = await res.json();
      setEvents(data.events || []);

      // Track custom RUM action — events loaded
      datadogRum.addAction('events_loaded', {
        count: data.events?.length || 0,
      });
    } catch (err) {
      datadogRum.addError(err as Error, { context: 'fetch_events' });
      console.error('Failed to fetch events:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch odds for a specific sport
  const fetchOdds = useCallback(async (sport: string) => {
    const sportsToFetch = sport === 'all'
      ? ['football', 'soccer', 'basketball', 'baseball', 'hockey']
      : [sport];

    for (const s of sportsToFetch) {
      try {
        const res = await fetch(`${ODDS_URL}/odds/bulk/${s}`);
        if (!res.ok) continue;
        const data = await res.json();
        setOddsMap(prev => {
          const updated = { ...prev };
          for (const item of (data.odds || [])) {
            updated[item.event_id] = item;
          }
          return updated;
        });
      } catch (err) {
        console.error(`Failed to fetch odds for ${s}:`, err);
      }
    }
  }, []);

  // Seed events if none exist
  const seedEvents = async () => {
    try {
      await fetch(`${ODDS_URL}/seed`, { method: 'POST' });
      await fetchEvents();
    } catch (err) {
      console.error('Seed failed:', err);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  useEffect(() => {
    if (events.length > 0) {
      fetchOdds(activeSport);
      // Refresh odds every 30 seconds
      const interval = setInterval(() => fetchOdds(activeSport), 30000);
      return () => clearInterval(interval);
    }
  }, [events, activeSport, fetchOdds]);

  const handleSelectBet = (bet: Bet) => {
    setSelectedBet(bet);
    // Track RUM action — selection clicked
    datadogRum.addAction('bet_selection_clicked', {
      event_id: bet.eventId,
      selection: bet.selection,
      odds: bet.odds,
      sport: bet.sport,
    });
  };

  const handlePlaceBet = async (stake: number) => {
    if (!selectedBet) return;

    const startTime = performance.now();

    try {
      // Track RUM action — bet placement started
      datadogRum.addAction('bet_placement_started', {
        event_id: selectedBet.eventId,
        selection: selectedBet.selection,
        stake,
      });

      const res = await fetch(`${BET_URL}/bets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          event_id: selectedBet.eventId,
          selection: selectedBet.selection,
          stake,
        }),
      });

      const duration = performance.now() - startTime;

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Bet placement failed');
      }

      const bet = await res.json();

      // Track successful bet — RUM custom action with full context
      datadogRum.addAction('bet_placed_success', {
        bet_id: bet.bet_id,
        event_id: selectedBet.eventId,
        selection: selectedBet.selection,
        stake,
        odds: bet.odds,
        potential_payout: bet.potential_payout,
        duration_ms: Math.round(duration),
      });

      setPlacedBets(prev => [bet, ...prev]);
      setSelectedBet(null);
      setActiveTab('mybets');

    } catch (err) {
      // Track failed bet — appears in RUM Error Tracking
      datadogRum.addError(err as Error, {
        event_id: selectedBet.eventId,
        selection: selectedBet.selection,
        stake,
      });
      throw err;
    }
  };

  const filteredEvents = activeSport === 'all'
    ? events
    : events.filter(e => e.sport === activeSport);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-5xl mb-4 animate-pulse">🦅</div>
          <p className="text-gray-400">Loading odds...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Header />

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Sport tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {SPORTS.map(sport => (
            <button
              key={sport}
              className={`sport-tab whitespace-nowrap capitalize ${activeSport === sport ? 'active' : ''}`}
              onClick={() => {
                setActiveSport(sport);
                datadogRum.addAction('sport_tab_clicked', { sport });
              }}
            >
              {sport === 'all' ? '🏆 All Sports' :
               sport === 'football' ? '🏈 Football' :
               sport === 'soccer' ? '⚽ Soccer' :
               sport === 'basketball' ? '🏀 Basketball' :
               sport === 'baseball' ? '⚾ Baseball' :
               sport === 'hockey' ? '🏒 Hockey' : sport}
            </button>
          ))}
        </div>

        {/* Mobile tab switcher */}
        <div className="flex md:hidden gap-2 mb-4">
          <button
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'odds' ? 'bg-purple-700 text-white' : 'bg-gray-800 text-gray-400'}`}
            onClick={() => setActiveTab('odds')}
          >
            Odds Board
          </button>
          <button
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'mybets' ? 'bg-purple-700 text-white' : 'bg-gray-800 text-gray-400'}`}
            onClick={() => setActiveTab('mybets')}
          >
            My Bets {placedBets.length > 0 && `(${placedBets.length})`}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main odds board */}
          <div className={`md:col-span-2 ${activeTab === 'mybets' ? 'hidden md:block' : ''}`}>
            {events.length === 0 ? (
              <div className="card text-center py-12">
                <div className="text-4xl mb-4">🏟️</div>
                <p className="text-gray-400 mb-4">No events available</p>
                <button
                  onClick={seedEvents}
                  className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-2 rounded-lg"
                >
                  Load Events
                </button>
              </div>
            ) : (
              <OddsBoard
                events={filteredEvents}
                oddsMap={oddsMap}
                selectedBet={selectedBet}
                onSelectBet={handleSelectBet}
              />
            )}
          </div>

          {/* Right sidebar */}
          <div className={`space-y-4 ${activeTab === 'odds' && 'hidden md:block'}`}>
            <BetSlip
              selectedBet={selectedBet}
              onPlaceBet={handlePlaceBet}
              onClear={() => setSelectedBet(null)}
            />
            <MyBets
              bets={placedBets}
              userId={userId}
              betServiceUrl={BET_URL}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
