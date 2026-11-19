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
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isUnmountedRef = useRef(false);

  const connect = useCallback(() => {
    if (!enabled || !projectId || typeof window === 'undefined' || isUnmountedRef.current) return;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    // Connect through proxy or direct API backend port 8008
    const wsUrl = `${protocol}//${host}/ws/projects/${projectId}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (isUnmountedRef.current) {
        ws.close();
        return;
      }
      setIsConnected(true);
      // Start ping heartbeat every 25 seconds
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      if (isUnmountedRef.current) return;
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
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (isUnmountedRef.current) return;
      setIsConnected(false);
      // Auto-reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        if (!isUnmountedRef.current) {
          connect();
        }
      }, 3000);
    };

    ws.onerror = (err) => {
      console.warn('WebSocket encountered error:', err);
      ws.close();
    };
  }, [projectId, enabled, onPatchReceived]);

  useEffect(() => {
    isUnmountedRef.current = false;
    connect();
    return () => {
      isUnmountedRef.current = true;
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
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
