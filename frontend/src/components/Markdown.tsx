import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function Markdown({ content }: { content: string }) {
  if (!content.trim()) {
    return <p className="text-sm text-muted-foreground">-</p>;
  }
  return (
    <div className="aura-prose">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
