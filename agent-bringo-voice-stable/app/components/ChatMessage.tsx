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
          // Agent messages: full markdown support
          <div className="prose prose-sm max-w-none prose-gray
            prose-headings:font-bold prose-headings:text-gray-900
            prose-p:text-gray-800 prose-p:leading-relaxed prose-p:my-2
            prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline prose-a:font-medium
            prose-strong:text-gray-900 prose-strong:font-semibold
            prose-em:text-gray-700 prose-em:italic
            prose-code:text-sm prose-code:bg-gray-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:font-mono prose-code:text-gray-800 prose-code:before:content-none prose-code:after:content-none
            prose-pre:bg-gray-900 prose-pre:text-gray-100 prose-pre:rounded-lg prose-pre:p-4
            prose-ul:my-2 prose-ul:list-disc prose-ul:pl-5 prose-ul:space-y-1
            prose-ol:my-2 prose-ol:list-decimal prose-ol:pl-5 prose-ol:space-y-1
            prose-li:text-gray-800 prose-li:leading-relaxed
            prose-blockquote:border-l-4 prose-blockquote:border-blue-300 prose-blockquote:pl-4 prose-blockquote:italic prose-blockquote:text-gray-600
            prose-hr:border-gray-200 prose-hr:my-4
            prose-table:text-sm prose-table:border-collapse
            prose-th:bg-gray-50 prose-th:font-semibold prose-th:text-gray-900 prose-th:border prose-th:border-gray-300 prose-th:p-2
            prose-td:border prose-td:border-gray-300 prose-td:p-2 prose-td:text-gray-800
            prose-img:rounded-lg prose-img:shadow-sm
          ">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Custom link handling - open in new tab
                a: ({ node, children, href, ...props }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                    {children}
                  </a>
                ),
                // Improve list rendering
                ul: ({ node, children, ...props }) => (
                  <ul className="space-y-1 my-2" {...props}>
                    {children}
                  </ul>
                ),
                ol: ({ node, children, ...props }) => (
                  <ol className="space-y-1 my-2" {...props}>
                    {children}
                  </ol>
                ),
                li: ({ node, children, ...props }) => (
                  <li className="text-gray-800 leading-relaxed" {...props}>
                    {children}
                  </li>
                ),
                // Better paragraph spacing
                p: ({ node, children, ...props }) => (
                  <p className="my-2 leading-relaxed last:mb-0 first:mt-0" {...props}>
                    {children}
                  </p>
                ),
                // Code blocks
                code: ({ node, inline, className, children, ...props }: any) => {
                  if (inline) {
                    return (
                      <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-gray-800" {...props}>
                        {children}
                      </code>
                    );
                  }
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
                // Strong/bold text
                strong: ({ node, children, ...props }) => (
                  <strong className="font-semibold text-gray-900" {...props}>
                    {children}
                  </strong>
                ),
                // Emphasized text
                em: ({ node, children, ...props }) => (
                  <em className="italic text-gray-700" {...props}>
                    {children}
                  </em>
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
