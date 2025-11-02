'use client';

import { useAutoScroll } from '@/hooks/useAutoScroll';
import { useTranslationRPC } from '@/hooks/useTranslationRPC';
import { TranslationData } from '@/lib/types';
import { useCallback, useRef, useState } from 'react';

export interface TranslationAlternateProps {
  className?: string;
  sourceLanguage: string;
  targetLanguage: string;
  getLanguageLabel: (lang: string) => string;
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

interface ConversationBubbleProps {
  text: string;
  type: 'original' | 'translation' | 'target-native';
  isInterim?: boolean;
}

// 对话气泡组件
function ConversationBubble({ 
  text, 
  type, 
  isInterim = false 
}: ConversationBubbleProps) {
  const bgColors = {
    'original': 'bg-gray-50 dark:bg-gray-900 border-gray-300',
    'translation': 'bg-green-50 dark:bg-green-950 border-green-300',
    'target-native': 'bg-blue-50 dark:bg-blue-950 border-blue-300',
  };

  return (
    <div 
      className={`${bgColors[type]} p-3 rounded-lg border ${isInterim ? 'border-2 border-dashed' : ''}`}
    >
      <p className={`text-base whitespace-pre-wrap break-words ${type === 'original' ? 'font-mono' : ''}`}>
        {text}
      </p>
    </div>
  );
}

export function TranslationAlternate({ 
  className, 
  sourceLanguage, 
  targetLanguage, 
  getLanguageLabel 
}: TranslationAlternateProps) {
  // 累积的对话记录（final 状态）
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  // 实时预览（interim 状态）
  const [interimOriginal, setInterimOriginal] = useState<string>('');
  const [interimOriginalLang, setInterimOriginalLang] = useState<string>('');
  const [interimTranslation, setInterimTranslation] = useState<string>('');
  const [isInterim, setIsInterim] = useState<boolean>(false);
  
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // 处理翻译数据
  const handleTranslation = useCallback((payload: TranslationData) => {
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
      setConversation((prev) => [
        ...prev,
        {
          original: payload.original,
          translation: payload.translation,
          timestamp: payload.timestamp,
        }
      ]);

      // 清除实时预览
      setInterimOriginal('');
      setInterimOriginalLang('');
      setInterimTranslation('');
      setIsInterim(false);
    }
  }, []);

  // 使用 RPC hook
  useTranslationRPC(handleTranslation);

  // 自动滚动
  useAutoScroll(scrollContainerRef, [conversation, isInterim]);

  // 判断是否需要显示原文
  const shouldShowOriginal = (item: ConversationItem) => {
    return item.translation || item.original.language !== targetLanguage;
  };

  // 判断是否显示为目标语言原生输入
  const isTargetNativeInput = (item: ConversationItem) => {
    return !item.translation && item.original.language === targetLanguage;
  };

  return (
    <div className={`flex flex-col h-full ${className || ''}`}>
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
            {/* 原始文本 */}
            {shouldShowOriginal(item) && (
              <ConversationBubble
                text={item.original.text}
                type="original"
              />
            )}

            {/* 翻译文本 */}
            {item.translation && (
              <ConversationBubble
                text={item.translation.text}
                type="translation"
              />
            )}

            {/* 目标语言原生输入 */}
            {isTargetNativeInput(item) && (
              <ConversationBubble
                text={item.original.text}
                type="target-native"
              />
            )}
          </div>
        ))}

        {/* 实时预览（interim 状态） */}
        {isInterim && (
          <div className="space-y-2">
            {/* 原始文本预览 */}
            {(interimTranslation || interimOriginalLang !== targetLanguage) && interimOriginal && (
              <ConversationBubble
                text={interimOriginal}
                type="original"
                isInterim
              />
            )}

            {/* 翻译预览 */}
            {interimTranslation && (
              <ConversationBubble
                text={interimTranslation}
                type="translation"
                isInterim
              />
            )}

            {/* 目标语言原生输入预览 */}
            {interimOriginalLang === targetLanguage && interimOriginal && !interimTranslation && (
              <ConversationBubble
                text={interimOriginal}
                type="target-native"
                isInterim
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
