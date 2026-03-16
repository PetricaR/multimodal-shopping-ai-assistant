import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessageProps {
  role: 'user' | 'agent';
  text: string;
  timestamp: string;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ role, text, timestamp }) => {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-200`}>
      <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? 'bg-gradient-to-br from-blue-600 to-blue-500 text-white rounded-br-sm shadow-md'
          : 'bg-white text-gray-800 border border-gray-100 rounded-bl-sm shadow-sm'
      }`}>
        {isUser ? (
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{text}</p>
        ) : (
          <div className="prose prose-sm max-w-none
            prose-p:text-gray-800 prose-p:leading-relaxed prose-p:my-1 prose-p:first:mt-0 prose-p:last:mb-0
            prose-strong:text-gray-900 prose-strong:font-semibold
            prose-em:text-gray-700
            prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline prose-a:font-medium
            prose-ul:my-1.5 prose-ul:pl-4 prose-li:my-0.5 prose-li:text-gray-800
            prose-ol:my-1.5 prose-ol:pl-4
            prose-hr:border-gray-200 prose-hr:my-2
            prose-code:text-blue-700 prose-code:bg-blue-50 prose-code:text-xs prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:font-mono prose-code:before:content-none prose-code:after:content-none
            prose-pre:bg-gray-50 prose-pre:border prose-pre:border-gray-200 prose-pre:text-gray-800 prose-pre:text-xs prose-pre:rounded-lg
          ">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // No headings — stripped by filter, but render cleanly if they slip through
                h1: ({ children }) => <p className="font-semibold text-gray-900 mt-1 mb-0.5">{children}</p>,
                h2: ({ children }) => <p className="font-semibold text-gray-900 mt-1 mb-0.5">{children}</p>,
                h3: ({ children }) => <p className="font-medium text-gray-800 mt-0.5">{children}</p>,
                // Links open in new tab
                a: ({ children, href }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{children}</a>
                ),
                // Code: light blue pill for inline, subtle panel for blocks
                code: ({ node, inline, children }: any) => (
                  inline
                    ? <code className="text-blue-700 bg-blue-50 text-xs px-1.5 py-0.5 rounded font-mono">{children}</code>
                    : <pre className="bg-gray-50 border border-gray-200 rounded-lg p-3 my-2 overflow-x-auto text-xs text-gray-700 font-mono"><code>{children}</code></pre>
                ),
              }}
            >
              {text}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};
