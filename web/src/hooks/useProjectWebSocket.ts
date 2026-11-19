'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { PatchDeltaEvent, PatchOperation } from '@/lib/patch';

interface UseProjectWebSocketOptions {
  projectId: string;
  onPatchReceived?: (delta: PatchDeltaEvent) => void;
  enabled?: boolean;
}

export function useProjectWebSocket({
  projectId,
  onPatchReceived,
  enabled = true,
}: UseProjectWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastVersion, setLastVersion] = useState<number | null>(null);
  const [lastPatches, setLastPatches] = useState<PatchOperation[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!enabled || !projectId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    // Connect through proxy or direct API backend port 8008
    const wsUrl = `${protocol}//${host}/ws/projects/${projectId}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      // Start ping heartbeat every 25 seconds
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'patch') {
          const delta = data as PatchDeltaEvent;
          setLastVersion(delta.version);
          setLastPatches(delta.patches);
          if (onPatchReceived) {
            onPatchReceived(delta);
          }
        }
      } catch (err) {
        console.error('Error parsing WebSocket message:', err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      // Auto-reconnect after 3 seconds
      setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.warn('WebSocket encountered error:', err);
      ws.close();
    };
  }, [projectId, enabled, onPatchReceived]);

  useEffect(() => {
    connect();
    return () => {
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    isConnected,
    lastVersion,
    lastPatches,
  };
}
