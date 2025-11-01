'use client';

import { useMaybeRoomContext } from '@livekit/components-react';
import { RpcInvocationData } from 'livekit-client';
import { useEffect, useRef, useState } from 'react';
import { useTypewriter } from '@/hooks/useTypewriter';

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

export interface SplitViewDisplayProps {
  className?: string;
}

export function SplitViewDisplay({ className }: SplitViewDisplayProps) {
  // 原文区域：累积的 final 原文 + 当前 interim
  const [accumulatedOriginal, setAccumulatedOriginal] = useState<string>('');
  const [latestOriginal, setLatestOriginal] = useState<string>('');
  const [currentInterim, setCurrentInterim] = useState<string>('');
  const [currentLanguage, setCurrentLanguage] = useState<string>('');
  
  // 译文区域：累积的所有 final 译文
  const [accumulatedTranslation, setAccumulatedTranslation] = useState<string>('');
  const [latestTranslation, setLatestTranslation] = useState<string>('');
  
  // 打字机模式
  const [originalTypewriterMode, setOriginalTypewriterMode] = useState<'character' | 'word'>('character');
  const [translationTypewriterMode, setTranslationTypewriterMode] = useState<'character' | 'word'>('character');
  
  // 控制是否显示实时输入（interim）
  const [showInterim, setShowInterim] = useState<boolean>(true);
  
  const room = useMaybeRoomContext();
  const originalScrollRef = useRef<HTMLDivElement>(null);
  const translationScrollRef = useRef<HTMLDivElement>(null);

  // 原文打字机效果（用于最新一句）
  const { displayedText: displayedOriginal, isTyping: isTypingOriginal } = useTypewriter(latestOriginal, {
    speed: originalTypewriterMode === 'character' ? 30 : 100,
    mode: originalTypewriterMode,
  });

  // 译文打字机效果（用于最新一句）
  const { displayedText: displayedTranslation, isTyping: isTypingTranslation } = useTypewriter(latestTranslation, {
    speed: translationTypewriterMode === 'character' ? 30 : 100,
    mode: translationTypewriterMode,
  });

  // Register RPC handler for receiving translation updates
  useEffect(() => {
    if (!room || !room.localParticipant) return;

    const handleReceiveTranslation = async (
      rpcInvocation: RpcInvocationData
    ): Promise<string> => {
      try {
        const payload = JSON.parse(rpcInvocation.payload) as TranslationData;

        if (payload && payload.original) {
          // 原文处理
          if (payload.type === 'interim') {
            // interim：更新当前 interim（覆盖，不累积）
            setCurrentInterim(payload.original.text);
            setCurrentLanguage(payload.original.language);
          } else if (payload.type === 'final') {
            // final：追加到累积原文，设置最新原文，清空 interim
            const newOriginal = payload.original.text;
            
            setAccumulatedOriginal((prev) => {
              const separator = prev ? '\n\n' : '';
              return prev + separator + newOriginal;
            });
            setLatestOriginal(newOriginal);
            setCurrentInterim('');
            setCurrentLanguage(payload.original.language);
          }

          // 译文处理：只处理有翻译的 final
          if (payload.type === 'final' && payload.translation) {
            const newTranslation = payload.translation.text;
            
            // 追加到累积译文
            setAccumulatedTranslation((prev) => {
              const separator = prev ? '\n\n' : '';
              return prev + separator + newTranslation;
            });
            
            // 设置最新译文，触发打字机效果
            setLatestTranslation(newTranslation);
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

  // 自动滚动到底部 - 原文区域
  useEffect(() => {
    if (originalScrollRef.current) {
      originalScrollRef.current.scrollTop = originalScrollRef.current.scrollHeight;
    }
  }, [accumulatedOriginal, currentInterim, displayedOriginal]);

  // 自动滚动到底部 - 译文区域
  useEffect(() => {
    if (translationScrollRef.current) {
      translationScrollRef.current.scrollTop = translationScrollRef.current.scrollHeight;
    }
  }, [accumulatedTranslation, displayedTranslation]);

  const getLanguageLabel = (lang: string): string => {
    const labels: Record<string, string> = {
      fr: '法语',
      en: '英语',
      zh: '中文',
    };
    return labels[lang] || lang.toUpperCase();
  };

  // 计算要显示的完整原文（已完成的 + 正在打字的）
  const getDisplayedOriginal = () => {
    if (!accumulatedOriginal) {
      return displayedOriginal;
    }
    
    const sentences = accumulatedOriginal.split('\n\n');
    if (sentences.length === 0) return displayedOriginal;
    
    const completedSentences = sentences.slice(0, -1).join('\n\n');
    
    if (completedSentences) {
      return completedSentences + '\n\n' + displayedOriginal;
    }
    return displayedOriginal;
  };

  // 计算要显示的完整译文（已完成的 + 正在打字的）
  const getDisplayedTranslation = () => {
    if (!accumulatedTranslation) {
      // 没有历史译文，只显示当前打字
      return displayedTranslation;
    }
    
    // 有历史译文，需要显示历史 + 正在打字的新句子
    const sentences = accumulatedTranslation.split('\n\n');
    if (sentences.length === 0) return displayedTranslation;
    
    // 移除最后一句（因为它正在打字中）
    const completedSentences = sentences.slice(0, -1).join('\n\n');
    
    if (completedSentences) {
      return completedSentences + '\n\n' + displayedTranslation;
    }
    return displayedTranslation;
  };

  return (
    <div className={`flex flex-col h-full ${className || ''}`}>
      {/* 上半部分：原文区域 */}
      <div className="flex-1 flex flex-col border-b-2 border-border min-h-0">
        <div className="bg-muted px-4 py-2 border-b border-border flex-shrink-0 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            原文
            {currentLanguage && (
              <span className="text-xs text-muted-foreground">({getLanguageLabel(currentLanguage)})</span>
            )}
          </h3>
          
          <div className="flex items-center gap-3">
            {/* 实时输入开关 */}
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={showInterim}
                onChange={(e) => setShowInterim(e.target.checked)}
                className="w-3.5 h-3.5 rounded border-gray-300 text-primary focus:ring-primary focus:ring-offset-0 cursor-pointer"
              />
              <span className="text-xs text-muted-foreground">实时输入</span>
            </label>
            
            {/* 打字机模式切换 */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => setOriginalTypewriterMode('character')}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  originalTypewriterMode === 'character'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-background text-muted-foreground hover:text-foreground'
                }`}
                title="逐字符显示（较慢，戏剧性强）"
              >
                逐字
              </button>
              <button
                onClick={() => setOriginalTypewriterMode('word')}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  originalTypewriterMode === 'word'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-background text-muted-foreground hover:text-foreground'
                }`}
                title="逐词显示（较快，流畅）"
              >
                逐词
              </button>
            </div>
          </div>
        </div>
        <div
          ref={originalScrollRef}
          className="flex-1 overflow-y-auto overflow-x-hidden p-6 bg-gray-50 dark:bg-gray-900 min-h-0"
        >
          {!accumulatedOriginal && !displayedOriginal && !currentInterim && (
            <div className="text-center text-muted-foreground py-8">
              等待输入...
            </div>
          )}
          
          {/* 完整原文（已完成的 + 正在打字的） */}
          {(accumulatedOriginal || displayedOriginal) && (
            <p className="text-base font-mono whitespace-pre-wrap break-words leading-relaxed">
              {getDisplayedOriginal()}
              {isTypingOriginal && (
                <span className="inline-block w-0.5 h-5 bg-foreground ml-0.5 animate-pulse" />
              )}
            </p>
          )}
          
          {/* 当前的 interim 文本（根据开关显示） */}
          {showInterim && currentInterim && (
            <div className={(accumulatedOriginal || displayedOriginal) ? 'mt-4' : ''}>
              <div className="inline-block px-3 py-2 bg-blue-100 dark:bg-blue-950 border-2 border-blue-300 border-dashed rounded">
                <span className="text-xs text-blue-500 animate-pulse mr-2">实时输入...</span>
                <span className="text-base font-mono whitespace-pre-wrap break-words">
                  {currentInterim}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 下半部分：译文区域 */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="bg-muted px-4 py-2 border-b border-border flex-shrink-0 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">译文（中文）</h3>
          
          {/* 打字机模式切换 */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setTranslationTypewriterMode('character')}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                translationTypewriterMode === 'character'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-muted-foreground hover:text-foreground'
              }`}
              title="逐字符显示（较慢，戏剧性强）"
            >
              逐字
            </button>
            <button
              onClick={() => setTranslationTypewriterMode('word')}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                translationTypewriterMode === 'word'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-muted-foreground hover:text-foreground'
              }`}
              title="逐词显示（较快，流畅）"
            >
              逐词
            </button>
          </div>
        </div>
        <div
          ref={translationScrollRef}
          className="flex-1 overflow-y-auto overflow-x-hidden p-6 bg-green-50 dark:bg-green-950 min-h-0"
        >
          {!accumulatedTranslation && !displayedTranslation && (
            <div className="text-center text-muted-foreground py-8">
              等待翻译...
            </div>
          )}
          
          {/* 完整译文（已完成的 + 正在打字的） */}
          {(accumulatedTranslation || displayedTranslation) && (
            <p className="text-base whitespace-pre-wrap break-words leading-relaxed">
              {getDisplayedTranslation()}
              {isTypingTranslation && (
                <span className="inline-block w-0.5 h-5 bg-foreground ml-0.5 animate-pulse" />
              )}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

