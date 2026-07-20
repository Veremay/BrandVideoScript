"use client";

import type { Components } from "streamdown";
import { Streamdown } from "streamdown";

const markdownComponents: Components = {
    p: ({ children }) => <p className="glacier-md-p">{children}</p>,
    h1: ({ children }) => <h1 className="glacier-md-h1">{children}</h1>,
    h2: ({ children }) => <h2 className="glacier-md-h2">{children}</h2>,
    h3: ({ children }) => <h3 className="glacier-md-h3">{children}</h3>,
    h4: ({ children }) => <h4 className="glacier-md-h4">{children}</h4>,
    h5: ({ children }) => <h5 className="glacier-md-h5">{children}</h5>,
    h6: ({ children }) => <h6 className="glacier-md-h6">{children}</h6>,
    ul: ({ children }) => <ul className="glacier-md-ul">{children}</ul>,
    ol: ({ children }) => <ol className="glacier-md-ol">{children}</ol>,
    li: ({ children }) => <li className="glacier-md-li">{children}</li>,
    blockquote: ({ children }) => <blockquote className="glacier-md-blockquote">{children}</blockquote>,
    hr: () => <hr className="glacier-md-hr" />,
    strong: ({ children }) => <strong className="glacier-md-strong">{children}</strong>,
    em: ({ children }) => <em className="glacier-md-em">{children}</em>,
    del: ({ children }) => <del className="glacier-md-del">{children}</del>,
    a: ({ href, children }) => (
      <a className="glacier-md-a" href={href} rel="noopener noreferrer" target="_blank">
        {children}
      </a>
    ),
    table: ({ children }) => (
      <div className="glacier-md-table-wrap">
        <table className="glacier-md-table">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="glacier-md-thead">{children}</thead>,
    tbody: ({ children }) => <tbody className="glacier-md-tbody">{children}</tbody>,
    tr: ({ children }) => <tr className="glacier-md-tr">{children}</tr>,
    th: ({ children }) => <th className="glacier-md-th">{children}</th>,
    td: ({ children }) => <td className="glacier-md-td">{children}</td>,
    pre: ({ children }) => <pre className="glacier-md-pre">{children}</pre>,
    inlineCode: ({ children }) => <code className="glacier-md-code">{children}</code>,
    code: ({ className, children, ...props }) => {
      const languageClass = className?.includes("language-") ? className : "";
      return (
        <code className={`glacier-md-code${languageClass ? ` ${languageClass}` : ""}`} {...props}>
          {children}
        </code>
      );
    }
  };

type CoordinatorMarkdownProps = {
  content: string;
  isAnimating?: boolean;
};

export function CoordinatorMarkdown({ content, isAnimating = false }: CoordinatorMarkdownProps) {
  return (
    <Streamdown
      animated
      className="glacier-md"
      components={markdownComponents}
      controls={false}
      isAnimating={isAnimating}
      lineNumbers={false}
      mode={isAnimating ? "streaming" : "static"}
    >
      {content}
    </Streamdown>
  );
}
