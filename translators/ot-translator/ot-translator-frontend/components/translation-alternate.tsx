'use client';

import { useAutoScroll } from '@/hooks/useAutoScroll';
import { useTranslationRPC } from '@/hooks/useTranslationRPC';
import { TranslationData } from '@/lib/types';
import React, { useCallback, useRef, useState } from 'react';

export interface TranslationAlternateProps {
  className?: string;
  sourceLanguage: string;
  targetLanguage: string;
  getLanguageLabel: (lang: string) => string;
}

interface ConversationItem {
  original: {
    full_text: string;
    language: string;
  };
  translation: {
    full_text: string;
    language: string;
  } | null;
  timestamp: number;
}

interface ConversationBubbleProps {
  text: string;
  type: 'original' | 'translation' | 'target-native';
  isInterim?: boolean;
  prevText?: string;
}

type ChangeType = 'same' | 'added' | 'modified';

interface TextChange {
  type: ChangeType;
  text: string;
  startIndex: number;
}

// 计算文本的增量变化
const computeTextChanges = (oldText: string, newText: string): TextChange[] => {
  const changes: TextChange[] = [];
  
  // 找到相同的前缀
  let commonPrefixLength = 0;
  const minLength = Math.min(oldText.length, newText.length);
  while (commonPrefixLength < minLength && oldText[commonPrefixLength] === newText[commonPrefixLength]) {
    commonPrefixLength++;
  }
  
  // 找到相同的后缀
  let commonSuffixLength = 0;
  const maxSuffixLength = minLength - commonPrefixLength;
  while (
    commonSuffixLength < maxSuffixLength &&
    oldText[oldText.length - 1 - commonSuffixLength] === newText[newText.length - 1 - commonSuffixLength]
  ) {
    commonSuffixLength++;
  }
  
  // 相同的前缀部分
  if (commonPrefixLength > 0) {
    changes.push({
      type: 'same',
      text: newText.slice(0, commonPrefixLength),
      startIndex: 0,
    });
  }
  
  // 中间变化的部分
  const oldMiddle = oldText.slice(commonPrefixLength, oldText.length - commonSuffixLength);
  const newMiddle = newText.slice(commonPrefixLength, newText.length - commonSuffixLength);
  
  if (newMiddle) {
    changes.push({
      type: !oldMiddle ? 'added' : 'modified',
      text: newMiddle,
      startIndex: commonPrefixLength,
    });
  }
  
  // 相同的后缀部分
  if (commonSuffixLength > 0) {
    changes.push({
      type: 'same',
      text: newText.slice(newText.length - commonSuffixLength),
      startIndex: newText.length - commonSuffixLength,
    });
  }
  
  return changes;
};

// 渲染带增量动画的文本
const renderTextWithAnimation = (currentText: string, prevText: string) => {
  if (!currentText) return null;
  if (!prevText) {
    return (
      <span className="animate-fade-in">
        {currentText}
      </span>
    );
  }
  
  const changes = computeTextChanges(prevText, currentText);
  
  return (
    <>
      {changes.map((change, index) => {
        const key = `${change.startIndex}-${index}`;
        
        if (change.type === 'same') {
          return <span key={key}>{change.text}</span>;
        } else {
          return (
            <span key={key} className="animate-fade-in">
              {change.text}
            </span>
          );
        }
      })}
    </>
  );
};

// 对话气泡组件 - 使用 React.memo 避免不必要的重渲染
const ConversationBubble = React.memo(({ 
  text, 
  type, 
  isInterim = false,
  prevText = ''
}: ConversationBubbleProps) => {
  const bgColors = {
    'original': 'bg-gray-50 dark:bg-gray-900 border-gray-300',
    'translation': 'bg-green-50 dark:bg-green-950 border-green-300',
    'target-native': 'bg-blue-50 dark:bg-blue-950 border-blue-300',
  };

  return (
    <div 
      className={`${bgColors[type]} p-2 rounded-lg border ${isInterim ? 'border-2 border-dashed' : ''}`}
    >
      <p className={`text-base whitespace-pre-wrap break-words ${type === 'original' ? 'font-mono' : ''}`}>
        {isInterim ? renderTextWithAnimation(text, prevText) : text}
      </p>
    </div>
  );
});

ConversationBubble.displayName = 'ConversationBubble';

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
  
  // 用于增量渲染的前一次文本状态
  const [prevInterimOriginal, setPrevInterimOriginal] = useState<string>('');
  const [prevInterimTranslation, setPrevInterimTranslation] = useState<string>('');
  const interimOriginalRef = useRef<string>('');
  const interimTranslationRef = useRef<string>('');
  
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // 处理翻译数据
  const handleTranslation = useCallback((payload: TranslationData) => {
    if (payload.type === 'interim') {
      // 使用 full_text（向后兼容 text）
      const newOriginal = payload.original.full_text || payload.original.text || '';
      const previousOriginal = interimOriginalRef.current;
      setPrevInterimOriginal(previousOriginal);
      setInterimOriginal(newOriginal);
      interimOriginalRef.current = newOriginal;
      
      setInterimOriginalLang(payload.original.language);
      setIsInterim(true);

      // 只在有新翻译时才更新，否则保持原有翻译不变
      if (payload.translation) {
        const newTranslation = payload.translation.full_text || payload.translation.text || '';
        const previousTranslation = interimTranslationRef.current;
        setPrevInterimTranslation(previousTranslation);
        setInterimTranslation(newTranslation);
        interimTranslationRef.current = newTranslation;
      }
      // 如果 payload.translation 为 null，保持 interimTranslation 的当前值不变
    } else if (payload.type === 'final') {
      // Final 状态：追加到对话记录，使用 full_text
      const originalText = payload.original.full_text || payload.original.text || '';
      const translationText = payload.translation?.full_text || payload.translation?.text || '';
      
      setConversation((prev) => [
        ...prev,
        {
          original: {
            full_text: originalText,
            language: payload.original.language,
          },
          translation: payload.translation ? {
            full_text: translationText,
            language: payload.translation.language,
          } : null,
          timestamp: payload.timestamp,
        }
      ]);

      // 清除实时预览
      setInterimOriginal('');
      setInterimOriginalLang('');
      setInterimTranslation('');
      setPrevInterimOriginal('');
      setPrevInterimTranslation('');
      interimOriginalRef.current = '';
      interimTranslationRef.current = '';
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
        className="flex-1 overflow-y-auto p-3 space-y-2"
      >
        {/* 累积的对话记录 */}
        {conversation.length === 0 && !isInterim && (
          <div className="text-center text-muted-foreground py-8">
            等待输入...
          </div>
        )}

        {conversation.map((item, index) => (
          <div key={index}>
            {/* 有翻译：原文+译文在一个卡片中 */}
            {item.translation && (
              <div className="bg-card p-2 rounded-lg border border-border shadow-sm">
                {/* 原文部分 */}
                <div className="pb-1.5">
                  <p className="text-base whitespace-pre-wrap break-words font-mono">
                    {item.original.full_text}
                  </p>
                </div>
                
                {/* 虚线分割 */}
                <div className="border-t border-dashed border-border my-1.5"></div>
                
                {/* 译文部分 */}
                <div className="pt-1.5">
                  <p className="text-base whitespace-pre-wrap break-words">
                    {item.translation.full_text}
                  </p>
                </div>
              </div>
            )}

            {/* 无翻译：目标语言原生输入，单独卡片 */}
            {isTargetNativeInput(item) && (
              <ConversationBubble
                text={item.original.full_text}
                type="target-native"
              />
            )}
          </div>
        ))}

        {/* 实时预览（interim 状态） */}
        {isInterim && (
          <div>
            {/* 需要翻译的内容：原文+译文在一个卡片中（实时预览） */}
            {interimOriginal && interimOriginalLang !== targetLanguage && (
              <div className="bg-card p-2 rounded-lg border-2 border-dashed border-primary/50 shadow-sm">
                {/* 原文部分 */}
                <div className="pb-1.5">
                  <p className="text-base whitespace-pre-wrap break-words font-mono">
                    {renderTextWithAnimation(interimOriginal, prevInterimOriginal)}
                  </p>
                </div>
                
                {/* 虚线分割 */}
                <div className="border-t border-dashed border-border my-1.5"></div>
                
                {/* 译文部分 - 可能还在翻译中 */}
                <div className="pt-1.5">
                  {interimTranslation ? (
                    <p className="text-base whitespace-pre-wrap break-words">
                      {renderTextWithAnimation(interimTranslation, prevInterimTranslation)}
                    </p>
                  ) : (
                    <p className="text-base text-muted-foreground/50">
                      翻译中...
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* 目标语言原生输入预览（无翻译） */}
            {interimOriginalLang === targetLanguage && interimOriginal && (
              <ConversationBubble
                text={interimOriginal}
                type="target-native"
                isInterim
                prevText={prevInterimOriginal}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
