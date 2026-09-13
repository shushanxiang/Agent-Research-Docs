// ResearchStreamChatView — 显示 useResearchStream 通道的消息流
// 用于首次 plan 生成 + plan 确认后的研究流程（与 LangGraph SDK 通道共存）

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, Copy, CopyCheck } from "lucide-react";
import { InputForm } from "@/components/InputForm";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  ActivityTimeline,
  ProcessedEvent,
} from "@/components/ActivityTimeline";

type MdComponentProps = {
  className?: string;
  children?: React.ReactNode;
  [key: string]: any;
};

const mdComponents = {
  h1: ({ className, children, ...props }: MdComponentProps) => (
    <h1 className={cn("text-2xl font-bold mt-4 mb-2", className)} {...props}>
      {children}
    </h1>
  ),
  h2: ({ className, children, ...props }: MdComponentProps) => (
    <h2 className={cn("text-xl font-bold mt-3 mb-2", className)} {...props}>
      {children}
    </h2>
  ),
  h3: ({ className, children, ...props }: MdComponentProps) => (
    <h3 className={cn("text-lg font-bold mt-3 mb-1", className)} {...props}>
      {children}
    </h3>
  ),
  p: ({ className, children, ...props }: MdComponentProps) => (
    <p className={cn("mb-3 leading-7", className)} {...props}>
      {children}
    </p>
  ),
  a: ({ className, children, href, ...props }: MdComponentProps) => (
    <Badge className="text-xs mx-0.5">
      <a
        className={cn("text-blue-400 hover:text-blue-300 text-xs", className)}
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        {children}
      </a>
    </Badge>
  ),
  ul: ({ className, children, ...props }: MdComponentProps) => (
    <ul className={cn("list-disc pl-6 mb-3", className)} {...props}>
      {children}
    </ul>
  ),
  ol: ({ className, children, ...props }: MdComponentProps) => (
    <ol className={cn("list-decimal pl-6 mb-3", className)} {...props}>
      {children}
    </ol>
  ),
  li: ({ className, children, ...props }: MdComponentProps) => (
    <li className={cn("mb-1", className)} {...props}>
      {children}
    </li>
  ),
  blockquote: ({ className, children, ...props }: MdComponentProps) => (
    <blockquote
      className={cn(
        "border-l-4 border-neutral-600 pl-4 italic my-3 text-sm",
        className
      )}
      {...props}
    >
      {children}
    </blockquote>
  ),
  code: ({ className, children, ...props }: MdComponentProps) => (
    <code
      className={cn(
        "bg-neutral-900 rounded px-1 py-0.5 font-mono text-xs",
        className
      )}
      {...props}
    >
      {children}
    </code>
  ),
  pre: ({ className, children, ...props }: MdComponentProps) => (
    <pre
      className={cn(
        "bg-neutral-900 p-3 rounded-lg overflow-x-auto font-mono text-xs my-3",
        className
      )}
      {...props}
    >
      {children}
    </pre>
  ),
  hr: ({ className, ...props }: MdComponentProps) => (
    <hr className={cn("border-neutral-600 my-4", className)} {...props} />
  ),
};

interface ResearchStreamChatViewProps {
  messages: Array<{ type: string; content: string; id: string }>;
  isLoading: boolean;
  liveActivityEvents: ProcessedEvent[];
  /** 当前正在流式输出的节点名称（null 表示非流式状态） */
  streamingNode: string | null;
  /** 当前节点已流式输出的累计文本 */
  streamingContent: string;
  onSubmit: (inputValue: string, effort: string, model: string) => void;
  onCancel: () => void;
  scrollAreaRef: React.RefObject<HTMLDivElement | null>;
}

export function ResearchStreamChatView({
  messages,
  isLoading,
  liveActivityEvents,
  streamingNode,
  streamingContent,
  onSubmit,
  onCancel,
  scrollAreaRef,
}: ResearchStreamChatViewProps) {
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [researchStarted, setResearchStarted] = useState(false);
  const inputFormRef = React.useRef<any>(null);

  const handleCopy = async (text: string, messageId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (err) {
      console.error("复制失败: ", err);
    }
  };

  // "需求确认"按钮点击事件
  const handleStartResearch = () => {
    if (inputFormRef.current?.setInputValue && inputFormRef.current?.submitInput) {
      inputFormRef.current.setInputValue("需求确认");
      inputFormRef.current.submitInput("需求确认");
      setResearchStarted(true);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <ScrollArea className="flex-1 overflow-y-auto" ref={scrollAreaRef}>
        <div className="p-4 md:p-6 space-y-2 max-w-4xl mx-auto pt-16">
          {messages.map((message, index) => (
            <div key={message.id || `msg-${index}`} className="space-y-6">
              <div
                className={`flex items-start gap-3 ${
                  message.type === "human" ? "justify-end" : ""
                }`}
              >
                {message.type === "human" ? (
                  <div className="text-white rounded-3xl break-words min-h-7 bg-neutral-700 max-w-[100%] sm:max-w-[90%] px-4 pt-3 rounded-br-lg">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                      {typeof message.content === "string"
                        ? message.content
                        : JSON.stringify(message.content)}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="relative break-words flex flex-col">
                    {liveActivityEvents.length > 0 && (
                      <div className="mb-3 border-b border-neutral-700 pb-3 text-xs">
                        <ActivityTimeline
                          processedEvents={liveActivityEvents}
                          isLoading={isLoading}
                          title="researching"
                        />
                      </div>
                    )}
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                      {typeof message.content === "string"
                        ? message.content
                        : JSON.stringify(message.content)}
                    </ReactMarkdown>
                    {message.content && (
                      <Button
                        variant="default"
                        className="cursor-pointer bg-neutral-700 border-neutral-600 text-neutral-300 self-end"
                        onClick={() => handleCopy(message.content, message.id)}
                      >
                        {copiedMessageId === message.id ? "已复制" : "复制"}
                        {copiedMessageId === message.id ? <CopyCheck /> : <Copy />}
                      </Button>
                    )}
                  </div>
                )}
              </div>
              {/* 在最后一条 AI 消息后显示"需求确认"按钮（仅当处于 plan 待确认状态时） */}
              {index === messages.length - 1 &&
                message.type === "ai" &&
                !researchStarted &&
                !isLoading &&
                !liveActivityEvents.some(e => e.title === "最终确定答案") && (
                  <div className="flex items-start gap-3">
                    <div className="relative group max-w-[85%] md:max-w-[80%] rounded-xl p-3 shadow-sm break-words bg-neutral-800 text-neutral-100">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-neutral-400">
                          确认以上研究方向后，点击"需求确认"开始深度研究
                        </span>
                        <Button
                          variant="default"
                          className="bg-neutral-700 hover:bg-neutral-600 cursor-pointer text-sm"
                          onClick={handleStartResearch}
                        >
                          需求确认
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
            </div>
          ))}
          {/* 流式内容气泡（实时 token 累积渲染） */}
          {streamingContent && (
            <div className="flex items-start gap-3">
              <div className="relative break-words flex flex-col w-full max-w-[85%] md:max-w-[80%] bg-neutral-800 text-neutral-100 rounded-xl rounded-bl-none p-3 shadow-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                  {streamingContent}
                </ReactMarkdown>
                <span className="text-xs text-neutral-500 mt-1 inline-flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {streamingNode === "generate_plan"
                    ? "正在生成计划..."
                    : streamingNode === "outline"
                    ? "正在生成提纲..."
                    : streamingNode === "draft"
                    ? "正在撰写草稿..."
                    : streamingNode === "cite_and_polish"
                    ? "正在润色和引用..."
                    : "正在生成..."}
                </span>
              </div>
            </div>
          )}
          {isLoading && !streamingContent && (
            <div className="flex items-start gap-3 mt-3">
              <div className="relative group max-w-[85%] md:max-w-[80%] rounded-xl p-3 shadow-sm break-words bg-neutral-800 text-neutral-100 rounded-bl-none w-full min-h-[56px]">
                <div className="flex items-center justify-start h-full">
                  <Loader2 className="h-5 w-5 animate-spin text-neutral-400 mr-2" />
                  <span>处理中...</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
      <InputForm
        ref={inputFormRef}
        onSubmit={onSubmit}
        isLoading={isLoading}
        onCancel={onCancel}
        hasHistory={messages.length > 0}
      />
    </div>
  );
}
