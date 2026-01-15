import { useCallback, useEffect, useRef, useState } from "react";

type SocketStatus = "idle" | "connecting" | "open" | "closed" | "error";

interface SocketState {
  status: SocketStatus;
  lastMessage?: MessageEvent;
  send: (payload: string) => void;
  close: () => void;
}

export const useSocket = (url?: string): SocketState => {
  const socketRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<SocketStatus>("idle");
  const [lastMessage, setLastMessage] = useState<MessageEvent | undefined>();

  useEffect(() => {
    if (!url) {
      return;
    }
    setStatus("connecting");
    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => setStatus("open");
    socket.onclose = () => setStatus("closed");
    socket.onerror = () => setStatus("error");
    socket.onmessage = (event) => setLastMessage(event);

    return () => {
      socket.close();
    };
  }, [url]);

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

