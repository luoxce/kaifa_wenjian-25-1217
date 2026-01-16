import { useCallback, useEffect, useRef, useState } from "react";

type SocketStatus = "idle" | "connecting" | "open" | "closed" | "error";

interface SocketState {
  status: SocketStatus;
  lastMessage?: MessageEvent;
  send: (payload: string) => void;
  close: () => void;
}

interface SocketOptions {
  reconnect?: boolean;
  reconnectIntervalMs?: number;
  maxRetries?: number;
}

export const useSocket = (url?: string, options?: SocketOptions): SocketState => {
  const socketRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<SocketStatus>("idle");
  const [lastMessage, setLastMessage] = useState<MessageEvent | undefined>();
  const retryRef = useRef(0);
  const opts = {
    reconnect: true,
    reconnectIntervalMs: 1500,
    maxRetries: 10,
    ...options,
  };

  useEffect(() => {
    if (!url) {
      return;
    }
    let active = true;
    let timeout: number | undefined;

    const connect = () => {
      if (!active) return;
      setStatus("connecting");
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
        retryRef.current = 0;
        setStatus("open");
      };
      socket.onclose = () => {
        setStatus("closed");
        if (opts.reconnect && retryRef.current < (opts.maxRetries ?? 0)) {
          retryRef.current += 1;
          timeout = window.setTimeout(connect, opts.reconnectIntervalMs);
        }
      };
      socket.onerror = () => {
        setStatus("error");
        socket.close();
      };
      socket.onmessage = (event) => setLastMessage(event);
    };

    connect();

    return () => {
      active = false;
      if (timeout) {
        window.clearTimeout(timeout);
      }
      socketRef.current?.close();
    };
  }, [url, opts.maxRetries, opts.reconnect, opts.reconnectIntervalMs]);

  const send = useCallback((payload: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(payload);
    }
  }, []);

  const close = useCallback(() => {
    socketRef.current?.close();
  }, []);

  return { status, lastMessage, send, close };
};
