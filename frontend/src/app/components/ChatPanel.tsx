import { useRef, useEffect, useState } from 'react';
import { Send, MessageSquare, X } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ScrollArea } from './ui/scroll-area';
import { Badge } from './ui/badge';
import { designTokens } from '../design-system';

interface ChatMessage {
  role: 'user' | 'assistant';
  message: string;
}

const formatAssistantMessage = (message: string) => {
  if (!message) return message;

  // Insert line breaks before numbered list items like "1.", "2.", etc.
  const formatted = message.replace(/(\d+)\.\s+/g, '\n$1. ');
  return formatted.trim();
};

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  docId?: string;
  currentTime?: number;
  currentSlideIndex?: number;
}

export default function ChatPanel({
  isOpen,
  onClose,
  docId,
  currentTime = 0,
  currentSlideIndex = 0,
}: ChatPanelProps) {
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      message: "Hi there! I'm your AI assistant. Feel free to ask me any questions about this video. I can help you understand the content better.",
    },
  ]);
  const [chatMessage, setChatMessage] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatScrollRef.current) {
      setTimeout(() => {
        if (chatScrollRef.current) {
          chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
        }
      }, 100);
    }
  }, [chatHistory, isThinking]);

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatMessage.trim() || isThinking) return;

    // Add user message
    setChatHistory((prev) => [...prev, { role: 'user', message: chatMessage }]);
    setIsThinking(true);

    // Send to backend agent
    (async () => {
      try {
        const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
        const resp = await fetch(`${API_BASE}/agent/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            doc_id: docId || '',
            message: chatMessage,
            video_time: currentTime,
            slide_index: currentSlideIndex,
          }),
        });

        if (!resp.ok) throw new Error(`Agent API error ${resp.status}`);

        const data = await resp.json();
        const assistantMsg = formatAssistantMessage(data?.answer || "I couldn't generate a response. Please try again.");
        setChatHistory((prev) => [...prev, { role: 'assistant', message: assistantMsg }]);
      } catch (err) {
        // Fallback response
        const fallbackResponses = [
          `That's a great question! Based on where we are in the video (${Math.floor(
            currentTime
          )} seconds), I'd say this relates to the key concepts being presented.`,
          `I can help with that! The presentation covers this topic in detail. Would you like me to explain it further?`,
          `That's an interesting point! The video discusses ${currentSlideIndex + 1} main topics. This seems relevant to what we're learning.`,
          `Good question! Let me help clarify this based on the content we've covered so far.`,
        ];
        const randomResponse =
          fallbackResponses[Math.floor(Math.random() * fallbackResponses.length)];
        setChatHistory((prev) => [...prev, { role: 'assistant', message: randomResponse }]);
      } finally {
        setIsThinking(false);
      }
    })();

    setChatMessage('');
  };

  if (!isOpen) return null;

  return (
    <div className="w-96 bg-white/95 backdrop-blur-md border-l border-indigo-100 flex flex-col h-full overflow-hidden rounded-l-2xl shadow-lg">
      {/* Header */}
      <div className="p-4 border-b border-indigo-100 bg-gradient-to-r from-indigo-50 to-purple-50 flex-shrink-0 rounded-2xl m-3 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center">
              <MessageSquare className="w-4 h-4 text-white" />
            </div>
            <h3 className="font-semibold text-slate-900">Chat Assistant</h3>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="bg-gradient-to-r from-emerald-500 to-teal-500 text-white border-0">
              <MessageSquare className="w-3 h-3 mr-1" />
              AI Powered
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="text-slate-500 hover:text-slate-900 hover:bg-slate-100 h-8 w-8 p-0"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
        <p className="text-xs text-slate-600 mt-2">Ask questions about the video content</p>
      </div>

      {/* Chat Messages */}
      <ScrollArea className="flex-1 p-4 min-h-0 overflow-hidden" ref={chatScrollRef}>
        <div className="space-y-4">
          {chatHistory.map((chat, index) => (
            <div
              key={index}
              className={`flex ${chat.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  chat.role === 'user'
                    ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white'
                    : 'bg-gradient-to-br from-slate-100 to-slate-50 text-slate-900 border border-slate-200'
                }`}
              >
                {chat.role === 'assistant' && (
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-5 h-5 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-full flex items-center justify-center">
                      <MessageSquare className="w-3 h-3 text-white" />
                    </div>
                    <span className="text-xs font-semibold text-indigo-600">AI Assistant</span>
                  </div>
                )}
                <div className="text-sm leading-relaxed break-words">
                  {chat.message.split('\n').map((line, i) => (
                    <div
                      key={i}
                      className={`whitespace-pre-wrap ${/^\s*\d+\./.test(line) ? 'ml-4' : ''}`}
                    >
                      {line}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
          {isThinking && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl px-4 py-3 bg-slate-100 text-slate-800 border border-slate-200 flex items-center gap-3">
                <span className="h-2.5 w-2.5 rounded-full bg-slate-500 animate-pulse" />
                <span className="text-sm">Typing...</span>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="p-4 border-t border-indigo-100 bg-white flex-shrink-0">
        <form onSubmit={handleSendMessage} className="flex gap-2">
          <Input
            value={chatMessage}
            onChange={(e) => setChatMessage(e.target.value)}
            placeholder="Ask about this video..."
            className="flex-1 border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
          />
          <Button
            type="submit"
            disabled={!chatMessage.trim() || isThinking}
            className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}
