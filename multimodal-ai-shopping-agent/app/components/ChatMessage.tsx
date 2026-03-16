import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessageProps {
  role: 'user' | 'agent';
  text: string;
  timestamp: string;
  isStreaming?: boolean;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ role, text, timestamp, isStreaming = false }) => {
  const isUser = role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end animate-in fade-in slide-in-from-bottom-1 duration-200">
        <div className="flex flex-col items-end gap-1 max-w-[82%]">
          <div className="bg-gradient-to-br from-blue-600 to-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-2.5 shadow-sm">
            <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">{text}</p>
          </div>
          <span className="text-[10px] text-gray-400 px-1">{timestamp}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2.5 animate-in fade-in slide-in-from-bottom-1 duration-200">
      {/* Avatar */}
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
        <svg className="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="currentColor">
          <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.937A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
        </svg>
      </div>

      {/* Bubble + meta */}
      <div className="flex flex-col gap-1 max-w-[82%]">
        <div className="flex items-baseline gap-1.5">
          <span className="text-[10px] font-semibold text-gray-500">Shopping AI</span>
          <span className="text-[10px] text-gray-400">{timestamp}</span>
        </div>
        <div className="bg-white text-gray-800 rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm leading-relaxed border border-gray-100 shadow-sm break-words relative pb-4">
          <div className="markdown-body prose prose-sm prose-blue max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {text}
            </ReactMarkdown>
          </div>
          {isStreaming && (
            <span className="absolute bottom-2 right-4 inline-block w-1 h-3 bg-blue-500 animate-pulse border border-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
          )}
        </div>
      </div>
    </div>
  );
};
