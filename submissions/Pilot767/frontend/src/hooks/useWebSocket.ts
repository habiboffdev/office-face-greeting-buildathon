import { useEffect, useRef, useState } from 'react';
import type { WelcomePayload } from '../services/api';

const WS_URL = 'ws://127.0.0.1:8000/ws/display';

export function useDisplayWebSocket(onWelcome: (data: WelcomePayload) => void) {
  const [connected, setConnected] = useState(false);
  const callbackRef = useRef(onWelcome);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const aliveRef = useRef(true);
  callbackRef.current = onWelcome;

  useEffect(() => {
    aliveRef.current = true;

    const connect = () => {
      if (!aliveRef.current) return;

      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
      }

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (aliveRef.current) setConnected(true);
      };

      ws.onclose = () => {
        setConnected(false);
        if (aliveRef.current) {
          retryRef.current = setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === 'welcome') {
            callbackRef.current(data as WelcomePayload);
          }
        } catch {
          /* ignore */
        }
      };
    };

    connect();

    return () => {
      aliveRef.current = false;
      if (retryRef.current) clearTimeout(retryRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnected(false);
    };
  }, []);

  return { connected };
}
