'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useStudioStore } from '@/store/studioStore';
import { PatchDeltaEvent } from '@/lib/patch';

interface UseProjectSocketOptions {
  projectId: string;
  enabled?: boolean;
}

export function useProjectSocket({ projectId, enabled = true }: UseProjectSocketOptions) {
  const { applyPatchDelta, fetchManifest, setConnectionState, version } = useStudioStore();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!enabled || !projectId || typeof window === 'undefined') return;

    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    setConnectionState('connecting');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/projects/${projectId}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState('connected');
        reconnectAttemptsRef.current = 0;

        // Start ping heartbeat every 20 seconds
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
          }
        }, 20000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'patch') {
            const delta = data as PatchDeltaEvent;
            const currentVer = useStudioStore.getState().version;

            // Detect sequence gap: if incoming version skipped one or more versions, refetch
            if (delta.version > currentVer + 1) {
              console.warn(
                `Sequence gap detected (expected ${currentVer + 1}, received ${delta.version}). Refetching full manifest.`
              );
              fetchManifest(projectId);
            } else {
              applyPatchDelta(delta.version, delta.patches);
            }
          }
        } catch (err) {
          console.error('Failed to process WebSocket message:', err);
        }
      };

      ws.onclose = () => {
        setConnectionState('disconnected');
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

        // Exponential backoff reconnect
        const attempt = reconnectAttemptsRef.current;
        const delay = Math.min(1000 * Math.pow(1.5, attempt), 10000);
        reconnectAttemptsRef.current += 1;

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      };

      ws.onerror = (err) => {
        console.warn('Project WebSocket error:', err);
        setConnectionState('error');
        ws.close();
      };
    } catch (err) {
      console.error('WebSocket connection instantiation error:', err);
      setConnectionState('error');
    }
  }, [projectId, enabled, applyPatchDelta, fetchManifest, setConnectionState]);

  useEffect(() => {
    connect();

    return () => {
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);
}
