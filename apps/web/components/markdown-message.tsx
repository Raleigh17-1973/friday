"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { Components } from "react-markdown";

// Scoped components: only renders inside AI message bubbles.
// User messages use plain <p> and bypass this component entirely.
const MD_COMPONENTS: Components = {
  // Headings — downscaled inside a chat bubble
  h1: ({ children }) => <h3 className="md-h1">{children}</h3>,
  h2: ({ children }) => <h4 className="md-h2">{children}</h4>,
  h3: ({ children }) => <h5 className="md-h3">{children}</h5>,

  // Inline code
  code: ({ className, children, ...props }) => {
    const isBlock = Boolean(className); // rehype-highlight adds a language class on fenced blocks
    if (isBlock) {
      return (
        <code className={`md-code-block ${className ?? ""}`} {...props}>
          {children}
        </code>
      );
    }
    return <code className="md-code-inline">{children}</code>;
  },

  // Fenced code block wrapper
  pre: ({ children }) => <pre className="md-pre">{children}</pre>,

  // Paragraphs — use a div to avoid nested <p> issues when ReactMarkdown wraps block elements
  p: ({ children }) => <p className="md-p">{children}</p>,

  // Lists
  ul: ({ children }) => <ul className="md-ul">{children}</ul>,
  ol: ({ children }) => <ol className="md-ol">{children}</ol>,
  li: ({ children }) => <li className="md-li">{children}</li>,

  // Blockquote
  blockquote: ({ children }) => <blockquote className="md-blockquote">{children}</blockquote>,

  // Strong / em
  strong: ({ children }) => <strong className="md-strong">{children}</strong>,
  em: ({ children }) => <em className="md-em">{children}</em>,

  // Horizontal rule
  hr: () => <hr className="md-hr" />,

  // Tables (remark-gfm)
  table: ({ children }) => (
    <div className="md-table-wrap">
      <table className="md-table">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead>{children}</thead>,
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => <tr>{children}</tr>,
  th: ({ children }) => <th className="md-th">{children}</th>,
  td: ({ children }) => <td className="md-td">{children}</td>,

  // Links — open in new tab, safe rel
  a: ({ href, children }) => (
    <a
      href={href}
      className="md-link"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
};

export function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="md-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={MD_COMPONENTS}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
