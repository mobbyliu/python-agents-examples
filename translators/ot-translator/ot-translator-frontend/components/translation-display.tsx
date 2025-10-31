'use client';

import { useMaybeRoomContext } from '@livekit/components-react';
import { RpcInvocationData } from 'livekit-client';
import { useEffect, useRef, useState } from 'react';

export interface TranslationData {
  type: 'interim' | 'final';
  original: {
    text: string;
    language: string;
  };
  translation: {
    text: string;
    language: string;
  } | null;
  timestamp: number;
}

export interface TranslationDisplayProps {
  className?: string;
}

interface ConversationItem {
  original: {
    text: string;
    language: string;
  };
  translation: {
    text: string;
    language: string;
  } | null;
  timestamp: number;
}

export function TranslationDisplay({ className }: TranslationDisplayProps) {
  // 累积的对话记录（final 状态）
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  // 实时预览（interim 状态）
  const [interimOriginal, setInterimOriginal] = useState<string>('');
  const [interimOriginalLang, setInterimOriginalLang] = useState<string>('');
  const [interimTranslation, setInterimTranslation] = useState<string>('');
  const [isInterim, setIsInterim] = useState<boolean>(false);
  const room = useMaybeRoomContext();
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Register RPC handler for receiving translation updates
  useEffect(() => {
    if (!room || !room.localParticipant) return;

    const handleReceiveTranslation = async (
      rpcInvocation: RpcInvocationData
    ): Promise<string> => {
      try {
        const payload = JSON.parse(rpcInvocation.payload) as TranslationData;

        if (payload && payload.original) {
          if (payload.type === 'interim') {
            // 实时更新预览
            setInterimOriginal(payload.original.text);
            setInterimOriginalLang(payload.original.language);
            setIsInterim(true);

            if (payload.translation) {
              setInterimTranslation(payload.translation.text);
            } else {
              setInterimTranslation('');
            }
          } else if (payload.type === 'final') {
            // Final 状态：追加到对话记录
            setConversation((prev) => {
              const newItem: ConversationItem = {
                original: payload.original,
                translation: payload.translation,
                timestamp: payload.timestamp,
              };
              return [...prev, newItem];
            });

            // 清除实时预览
            setInterimOriginal('');
            setInterimOriginalLang('');
            setInterimTranslation('');
            setIsInterim(false);
          }

          return 'Success: Translation received';
        } else {
          return 'Error: Invalid translation data format';
        }
      } catch (error) {
        console.error('Error processing translation RPC:', error);
        return 'Error: ' + (error instanceof Error ? error.message : String(error));
      }
    };

    // Register RPC method
    room.localParticipant.registerRpcMethod('receive_translation', handleReceiveTranslation);

    return () => {
      if (room && room.localParticipant) {
        room.localParticipant.unregisterRpcMethod('receive_translation');
      }
    };
  }, [room]);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [conversation, isInterim]);

  const getLanguageLabel = (lang: string): string => {
    const labels: Record<string, string> = {
      fr: '法语',
      en: '英语',
      zh: '中文',
    };
    return labels[lang] || lang.toUpperCase();
  };

  return (
    <div className={`flex flex-col h-full ${className || ''}`}>
      {/* Conversation Display - Scrollable */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
      >
        {/* 累积的对话记录 */}
        {conversation.length === 0 && !isInterim && (
          <div className="text-center text-muted-foreground py-8">
            等待输入...
          </div>
        )}

        {conversation.map((item, index) => (
          <div key={index} className="space-y-2">
            {/* 原始文本 - 只显示非中文原文 */}
            {item.original.language !== 'zh' && (
              <div className="bg-gray-50 dark:bg-gray-900 p-3 rounded-lg border border-gray-300">
                <div className="text-xs text-muted-foreground mb-1">
                  {getLanguageLabel(item.original.language)}
                </div>
                <p className="text-base whitespace-pre-wrap break-words font-mono">
                  {item.original.text}
                </p>
              </div>
            )}

            {/* 翻译文本（如果有） */}
            {item.translation && (
              <div className="bg-green-50 dark:bg-green-950 p-3 rounded-lg border border-green-300">
                <div className="text-xs text-muted-foreground mb-1">
                  中文 (翻译)
                </div>
                <p className="text-base whitespace-pre-wrap break-words">
                  {item.translation.text}
                </p>
              </div>
            )}

            {/* 中文输入（无翻译，说明是直接说中文） */}
            {!item.translation && item.original.language === 'zh' && (
              <div className="bg-blue-50 dark:bg-blue-950 p-3 rounded-lg border border-blue-300">
                <div className="text-xs text-muted-foreground mb-1">
                  中文 (原始输入)
                </div>
                <p className="text-base whitespace-pre-wrap break-words">
                  {item.original.text}
                </p>
              </div>
            )}
          </div>
        ))}

        {/* 实时预览（interim 状态） */}
        {isInterim && (
          <div className="space-y-2">
            {/* 原始文本预览 - 只显示非中文原文（英语/法语等） */}
            {interimOriginalLang !== 'zh' && interimOriginal && (
              <div className="bg-blue-50 dark:bg-blue-950 p-3 rounded-lg border-2 border-blue-300 border-dashed">
                <div className="text-xs text-muted-foreground mb-1 flex items-center gap-2">
                  {getLanguageLabel(interimOriginalLang)}
                  <span className="text-blue-500 animate-pulse text-xs">实时输入中...</span>
                </div>
                <p className="text-base whitespace-pre-wrap break-words font-mono">
                  {interimOriginal}
                </p>
              </div>
            )}

            {/* 翻译预览 - 有翻译时才显示 */}
            {interimTranslation && (
              <div className="bg-green-50 dark:bg-green-950 p-3 rounded-lg border-2 border-green-300 border-dashed">
                <div className="text-xs text-muted-foreground mb-1 flex items-center gap-2">
                  中文 (翻译)
                  <span className="text-green-500 animate-pulse text-xs">翻译中...</span>
                </div>
                <p className="text-base whitespace-pre-wrap break-words">
                  {interimTranslation}
                </p>
              </div>
            )}

            {/* 如果只有中文原文（没有翻译），显示中文 */}
            {interimOriginalLang === 'zh' && interimOriginal && !interimTranslation && (
              <div className="bg-blue-50 dark:bg-blue-950 p-3 rounded-lg border-2 border-blue-300 border-dashed">
                <div className="text-xs text-muted-foreground mb-1 flex items-center gap-2">
                  {getLanguageLabel(interimOriginalLang)}
                  <span className="text-blue-500 animate-pulse text-xs">实时输入中...</span>
                </div>
                <p className="text-base whitespace-pre-wrap break-words">
                  {interimOriginal}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

