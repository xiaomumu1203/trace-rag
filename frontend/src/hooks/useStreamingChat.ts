"use client";

import { useCallback, useRef, useState } from "react";
import { chatApi, streamChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

export function useStreamingChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);

  const load = useCallback(async (chatId: number) => {
    setError(null);
    try {
      const savedMessages = await chatApi.messages(chatId);
      messagesRef.current = savedMessages;
      setMessages(savedMessages);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    }
  }, []);

  const send = useCallback(async (chatId: number, input: string) => {
    const userMsg: ChatMessage = { role: "user", content: input };
    const history = [...messagesRef.current, userMsg];
    messagesRef.current = [...history, { role: "assistant", content: "" }];
    setMessages(messagesRef.current);
    setIsLoading(true);
    setError(null);
    try {
      await streamChat(
        chatId,
        history,
        (text) => {
          const next = [...messagesRef.current];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: last.content + text };
          messagesRef.current = next;
          setMessages(next);
        },
        (sources) => {
          const next = [...messagesRef.current];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, sources };
          messagesRef.current = next;
          setMessages(next);
        }
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    messagesRef.current = [];
    setMessages([]);
    setError(null);
  }, []);

  return { messages, isLoading, error, send, load, reset };
}
