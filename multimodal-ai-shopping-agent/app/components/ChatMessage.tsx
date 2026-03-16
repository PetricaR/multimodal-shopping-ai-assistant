import React from 'react';

interface ChatMessageProps {
  role: 'user' | 'agent';
  text: string;
  timestamp: string;
}

/** Convert plain text with line breaks into React elements */
const renderText = (text: string) => {
  const parts = text.split('\n');
  return parts.map((line, i) => {
    // Render blank lines as spacers
    if (!line.trim()) {
      return <br key={i} />;
    }
    // Render list items
    if (/^[-•*]\s/.test(line)) {
      return (
        <div key={i} className="flex gap-2 my-0.5">
          <span className="text-blue-400 flex-shrink-0 mt-0.5">•</span>
          <span>{renderInline(line.replace(/^[-•*]\s/, ''))}</span>
        </div>
      );
    }
    // Numbered list
    if (/^\d+\.\s/.test(line)) {
      const match = line.match(/^(\d+)\.\s(.*)/);
      if (match) {
        return (
          <div key={i} className="flex gap-2 my-0.5">
            <span className="text-blue-400 flex-shrink-0 font-medium min-w-[1.2rem] text-right">{match[1]}.</span>
            <span>{renderInline(match[2])}</span>
          </div>
        );
      }
    }
    return <p key={i} className="my-0.5 leading-relaxed">{renderInline(line)}</p>;
  });
};

/** Handle inline bold/italic formatting only */
const renderInline = (text: string): React.ReactNode => {
  // Bold: **text**
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
    }
    // Italic: *text* or _text_
    const italic = part.split(/(\*[^*]+\*|_[^_]+_)/g);
    return italic.map((p, j) => {
      if ((p.startsWith('*') && p.endsWith('*')) || (p.startsWith('_') && p.endsWith('_'))) {
        return <em key={j}>{p.slice(1, -1)}</em>;
      }
      return <React.Fragment key={j}>{p}</React.Fragment>;
    });
  });
};

export const ChatMessage: React.FC<ChatMessageProps> = ({ role, text, timestamp }) => {
  const isUser = role === 'user';

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} gap-0.5 animate-in fade-in slide-in-from-bottom-2 duration-200`}>
      {/* Avatar + name row */}
      {!isUser && (
        <div className="flex items-center gap-1.5 px-1">
          <div className="w-5 h-5 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
            <svg className="w-3 h-3 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.937A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>
            </svg>
          </div>
          <span className="text-[10px] font-medium text-gray-400">Shopping AI</span>
          <span className="text-[10px] text-gray-300">{timestamp}</span>
        </div>
      )}

      <div className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm ${
        isUser
          ? 'bg-gradient-to-br from-blue-600 to-blue-500 text-white rounded-br-sm shadow-md'
          : 'bg-white text-gray-800 border border-gray-100 rounded-bl-sm shadow-sm'
      }`}>
        {isUser ? (
          <p className="whitespace-pre-wrap break-words leading-relaxed">{text}</p>
        ) : (
          <div className="text-sm text-gray-800 leading-relaxed break-words">
            {renderText(text)}
          </div>
        )}
      </div>

      {isUser && (
        <span className="text-[10px] text-gray-300 px-1">{timestamp}</span>
      )}
    </div>
  );
};
