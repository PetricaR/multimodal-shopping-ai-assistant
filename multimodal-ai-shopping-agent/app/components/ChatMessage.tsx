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
          ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-br-md shadow-md'
          : 'bg-white text-gray-800 border border-gray-200 rounded-bl-md shadow-sm'
      }`}>
        {/* Message content with markdown rendering */}
        {isUser ? (
          // User messages: simple text with line breaks
          <div className="whitespace-pre-wrap break-words">
            {text}
          </div>
        ) : (
          // Agent messages: full markdown support via @tailwindcss/typography
          <div className="prose prose-sm max-w-none
            prose-p:text-gray-800 prose-p:leading-relaxed prose-p:my-1.5
            prose-headings:font-semibold prose-headings:text-gray-900
            prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline
            prose-strong:font-semibold prose-strong:text-gray-900
            prose-code:text-xs prose-code:bg-gray-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:font-mono prose-code:before:content-none prose-code:after:content-none
            prose-pre:bg-gray-900 prose-pre:text-gray-100 prose-pre:rounded-lg prose-pre:text-xs
            prose-ul:my-2 prose-ul:pl-4 prose-ol:my-2 prose-ol:pl-4
            prose-li:text-gray-800 prose-li:my-0.5
            prose-blockquote:border-blue-300 prose-blockquote:text-gray-600
            prose-hr:border-gray-200
            prose-table:text-xs prose-th:bg-gray-50 prose-td:text-gray-800
          ">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ node, children, href, ...props }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
                ),
                code: ({ node, inline, className, children, ...props }: any) => (
                  inline
                    ? <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono text-gray-800 before:content-none after:content-none">{children}</code>
                    : <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 my-2 overflow-x-auto text-xs font-mono"><code>{children}</code></pre>
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
