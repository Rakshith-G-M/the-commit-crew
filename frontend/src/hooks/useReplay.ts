import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../api";
import type { ReplayState, ReplayStatus } from "../api/types";

export interface UseReplayResult {
  state: ReplayState | null;
  status: ReplayStatus | null;
  isRunning: boolean;
  speed: number;
  simTimestamp: string;
  readingsCount: number;
  anomaliesCount: number;
  start: () => Promise<void>;
  pause: () => Promise<void>;
  reset: () => Promise<void>;
  setSpeed: (speed: number) => Promise<void>;
  isConnected: boolean;
  mode: "websocket" | "polling";
}

export function useReplay(): UseReplayResult {
  const [state, setState] = useState<ReplayState | null>(null);
  const [status, setStatus] = useState<ReplayStatus | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [mode, setMode] = useState<"websocket" | "polling">("polling");
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  // Fallback poll function
  const fetchCurrent = useCallback(async () => {
    try {
      const data = await api.replayCurrent();
      setState(data);
      setStatus({
        running: data.running,
        speed: data.speed,
        sim_timestamp: data.sim_timestamp,
        readings_replayed: data.readings_replayed,
        anomalies_detected: data.anomalies_detected,
        channels_active: data.channels.length,
      });
      setIsConnected(true);
    } catch {
      setIsConnected(false);
    }
  }, []);

  // WebSocket connection management with automatic fallback
  useEffect(() => {
    let unmounted = false;

    function connectWs() {
      try {
        const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${proto}//${window.location.host}/ws/replay`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (unmounted) return;
          setIsConnected(true);
          setMode("websocket");
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
        };

        ws.onmessage = (event) => {
          if (unmounted) return;
          try {
            const data = JSON.parse(event.data) as ReplayState;
            setState(data);
            setStatus({
              running: data.running,
              speed: data.speed,
              sim_timestamp: data.sim_timestamp,
              readings_replayed: data.readings_replayed,
              anomalies_detected: data.anomalies_detected,
              channels_active: data.channels.length,
            });
            setIsConnected(true);
          } catch {
            // non-json or malformed
          }
        };

        ws.onerror = () => {
          if (unmounted) return;
          ws.close();
        };

        ws.onclose = () => {
          if (unmounted) return;
          setMode("polling");
          if (!pollTimerRef.current) {
            pollTimerRef.current = window.setInterval(fetchCurrent, 1000);
          }
        };
      } catch {
        setMode("polling");
        if (!pollTimerRef.current) {
          pollTimerRef.current = window.setInterval(fetchCurrent, 1000);
        }
      }
    }

    // Initial fetch to immediately populate UI
    fetchCurrent();
    connectWs();

    return () => {
      unmounted = true;
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [fetchCurrent]);

  const start = useCallback(async () => {
    try {
      const res = await api.replayStart();
      setStatus(res);
      await fetchCurrent();
    } catch (err) {
      console.error("Failed to start replay", err);
    }
  }, [fetchCurrent]);

  const pause = useCallback(async () => {
    try {
      const res = await api.replayPause();
      setStatus(res);
      await fetchCurrent();
    } catch (err) {
      console.error("Failed to pause replay", err);
    }
  }, [fetchCurrent]);

  const reset = useCallback(async () => {
    try {
      const res = await api.replayReset();
      setStatus(res);
      await fetchCurrent();
    } catch (err) {
      console.error("Failed to reset replay", err);
    }
  }, [fetchCurrent]);

  const setSpeed = useCallback(
    async (newSpeed: number) => {
      try {
        await api.replaySpeed(newSpeed);
        await fetchCurrent();
      } catch (err) {
        console.error("Failed to set replay speed", err);
      }
    },
    [fetchCurrent],
  );

  return {
    state,
    status,
    isRunning: status?.running ?? state?.running ?? false,
    speed: status?.speed ?? state?.speed ?? 10.0,
    simTimestamp: status?.sim_timestamp ?? state?.sim_timestamp ?? "",
    readingsCount: status?.readings_replayed ?? state?.readings_replayed ?? 0,
    anomaliesCount: status?.anomalies_detected ?? state?.anomalies_detected ?? 0,
    start,
    pause,
    reset,
    setSpeed,
    isConnected,
    mode,
  };
}
