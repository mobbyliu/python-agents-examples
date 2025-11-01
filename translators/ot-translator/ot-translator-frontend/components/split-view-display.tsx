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

export interface SplitViewDisplayProps {
  className?: string;
}

// 支持的语言列表
const SUPPORTED_LANGUAGES = [
  { code: 'en', name: '英语 (English)' },
  { code: 'zh', name: '中文 (Chinese)' },
  { code: 'fr', name: '法语 (French)' },
  { code: 'es', name: '西班牙语 (Spanish)' },
  { code: 'de', name: '德语 (German)' },
  { code: 'ja', name: '日语 (Japanese)' },
  { code: 'ko', name: '韩语 (Korean)' },
  { code: 'pt', name: '葡萄牙语 (Portuguese)' },
  { code: 'ru', name: '俄语 (Russian)' },
  { code: 'ar', name: '阿拉伯语 (Arabic)' },
];

export function SplitViewDisplay({ className }: SplitViewDisplayProps) {
  // 原文区域：累积的文本 + 当前显示的文本
  const [accumulatedOriginal, setAccumulatedOriginal] = useState<string>('');
  const [currentOriginal, setCurrentOriginal] = useState<string>('');
  const [originalHighlights, setOriginalHighlights] = useState<number[]>([]);
  const [currentLanguage, setCurrentLanguage] = useState<string>('');
  
  // 译文区域：累积的文本 + 当前显示的文本
  const [accumulatedTranslation, setAccumulatedTranslation] = useState<string>('');
  const [currentTranslation, setCurrentTranslation] = useState<string>('');
  const [translationHighlights, setTranslationHighlights] = useState<number[]>([]);
  
  const room = useMaybeRoomContext();
  const originalScrollRef = useRef<HTMLDivElement>(null);
  const translationScrollRef = useRef<HTMLDivElement>(null);
  
  // 语言配置
  const [sourceLanguage, setSourceLanguage] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('translation_source_language') || 'en';
    }
    return 'en';
  });
  const [targetLanguage, setTargetLanguage] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('translation_target_language') || 'zh';
    }
    return 'zh';
  });
  const [debounceMs, setDebounceMs] = useState<number>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('translation_debounce_ms');
      return saved ? parseInt(saved) : 500;
    }
    return 500;
  });
  const [showConfig, setShowConfig] = useState<boolean>(false);
  
  // 计算文本差异的位置（用于高亮）
  const findDifferentIndices = (oldText: string, newText: string): number[] => {
    const indices: number[] = [];
    const maxLen = Math.max(oldText.length, newText.length);
    
    for (let i = 0; i < maxLen; i++) {
      if (oldText[i] !== newText[i]) {
        indices.push(i);
      }
    }
    
    return indices;
  };

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
            // interim：直接更新当前文本，实时显示
            setCurrentOriginal(payload.original.text);
            setCurrentLanguage(payload.original.language);
          } else if (payload.type === 'final') {
            // final：检查差异，高亮后确认
            const newOriginal = payload.original.text;
            
            if (newOriginal !== currentOriginal) {
              // 有差异：高亮不同部分
              const diffIndices = findDifferentIndices(currentOriginal, newOriginal);
              setOriginalHighlights(diffIndices);
              
              // 300ms 后清除高亮
              setTimeout(() => setOriginalHighlights([]), 300);
            }
            
            // 更新文本
            setCurrentOriginal(newOriginal);
            
            // 追加到历史记录
            setAccumulatedOriginal((prev) => {
              const separator = prev ? '\n\n' : '';
              return prev + separator + newOriginal;
            });
            
            setCurrentLanguage(payload.original.language);
          }

          // 译文处理
          if (payload.translation) {
            if (payload.type === 'interim') {
              // interim 翻译：直接更新当前译文，实时显示
              setCurrentTranslation(payload.translation.text);
            } else if (payload.type === 'final') {
              // final 翻译：检查差异，高亮后确认
              const newTranslation = payload.translation.text;
              
              if (newTranslation !== currentTranslation) {
                // 有差异：高亮不同部分
                const diffIndices = findDifferentIndices(currentTranslation, newTranslation);
                setTranslationHighlights(diffIndices);
                
                // 300ms 后清除高亮
                setTimeout(() => setTranslationHighlights([]), 300);
              }
              
              // 更新文本
              setCurrentTranslation(newTranslation);
              
              // 追加到历史记录
              setAccumulatedTranslation((prev) => {
                const separator = prev ? '\n\n' : '';
                return prev + separator + newTranslation;
              });
            }
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
  }, [accumulatedOriginal, currentOriginal]);

  // 自动滚动到底部 - 译文区域
  useEffect(() => {
    if (translationScrollRef.current) {
      translationScrollRef.current.scrollTop = translationScrollRef.current.scrollHeight;
    }
  }, [accumulatedTranslation, currentTranslation]);

  const getLanguageLabel = (lang: string): string => {
    const langObj = SUPPORTED_LANGUAGES.find(l => l.code === lang);
    if (langObj) return langObj.name.split(' ')[0]; // 返回中文名称
    
    const labels: Record<string, string> = {
      fr: '法语',
      en: '英语',
      zh: '中文',
    };
    return labels[lang] || lang.toUpperCase();
  };

  // 更新配置并发送到后端
  const updateTranslationConfig = async () => {
    if (!room || !room.localParticipant) {
      console.warn('Room not connected, cannot update config');
      return;
    }

    try {
      // 保存到 localStorage
      localStorage.setItem('translation_source_language', sourceLanguage);
      localStorage.setItem('translation_target_language', targetLanguage);
      localStorage.setItem('translation_debounce_ms', debounceMs.toString());

      // 发送配置到后端
      const payload = {
        source: sourceLanguage,
        target: targetLanguage,
        debounce: debounceMs,
      };

      const result = await room.localParticipant.performRpc({
        destinationIdentity: '', // 发送到 agent
        method: 'update_translation_config',
        payload: JSON.stringify(payload),
      });

      console.log('Config updated successfully:', result);
      setShowConfig(false);
    } catch (error) {
      console.error('Failed to update config:', error);
    }
  };

  // 初始化时发送配置到后端
  useEffect(() => {
    if (room && room.localParticipant && room.remoteParticipants.size > 0) {
      // 延迟一下确保 agent 已经准备好
      const timer = setTimeout(() => {
        updateTranslationConfig();
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [room?.remoteParticipants.size]);

  // 渲染带高亮的文本
  const renderTextWithHighlights = (text: string, highlights: number[]) => {
    if (highlights.length === 0) {
      return text;
    }
    
    return (
      <>
        {text.split('').map((char, index) => (
          <span
            key={index}
            className={`${
              highlights.includes(index)
                ? 'bg-yellow-200 dark:bg-yellow-700 transition-colors duration-300'
                : ''
            }`}
          >
            {char}
          </span>
        ))}
      </>
    );
  };

  // 获取完整显示文本（累积的历史 + 当前句子）
  const getFullOriginalText = () => {
    if (!accumulatedOriginal && !currentOriginal) return '';
    if (!accumulatedOriginal) return currentOriginal;
    
    const sentences = accumulatedOriginal.split('\n\n');
    const completedSentences = sentences.slice(0, -1).join('\n\n');
    
    if (completedSentences) {
      return completedSentences + '\n\n' + currentOriginal;
    }
    return currentOriginal;
  };

  const getFullTranslationText = () => {
    if (!accumulatedTranslation && !currentTranslation) return '';
    if (!accumulatedTranslation) return currentTranslation;
    
    const sentences = accumulatedTranslation.split('\n\n');
    const completedSentences = sentences.slice(0, -1).join('\n\n');
    
    if (completedSentences) {
      return completedSentences + '\n\n' + currentTranslation;
    }
    return currentTranslation;
  };

  return (
    <div className={`flex flex-col h-full ${className || ''}`}>
      {/* 配置面板 */}
      {showConfig && (
        <div className="bg-muted border-b border-border p-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold">翻译配置</h3>
              <button
                onClick={() => setShowConfig(false)}
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                ✕
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* 源语言选择 */}
              <div>
                <label className="block text-xs text-muted-foreground mb-1">源语言</label>
                <select
                  value={sourceLanguage}
                  onChange={(e) => setSourceLanguage(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-border rounded bg-background"
                >
                  {SUPPORTED_LANGUAGES.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.name}
                    </option>
                  ))}
                </select>
              </div>
              
              {/* 目标语言选择 */}
              <div>
                <label className="block text-xs text-muted-foreground mb-1">目标语言</label>
                <select
                  value={targetLanguage}
                  onChange={(e) => setTargetLanguage(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-border rounded bg-background"
                >
                  {SUPPORTED_LANGUAGES.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.name}
                    </option>
                  ))}
                </select>
              </div>
              
              {/* 防抖延迟 */}
              <div>
                <label className="block text-xs text-muted-foreground mb-1">
                  防抖延迟: {debounceMs}ms
                </label>
                <input
                  type="range"
                  min="100"
                  max="1000"
                  step="50"
                  value={debounceMs}
                  onChange={(e) => setDebounceMs(parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>更快</span>
                  <span>更稳</span>
                </div>
              </div>
            </div>
            
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setShowConfig(false)}
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
              >
                取消
              </button>
              <button
                onClick={updateTranslationConfig}
                className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded hover:opacity-90"
              >
                保存配置
              </button>
            </div>
          </div>
        </div>
      )}
      
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
            {/* 配置按钮 */}
            <button
              onClick={() => setShowConfig(!showConfig)}
              className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-background rounded transition-colors"
              title="翻译配置"
            >
              ⚙️ 配置
            </button>
          </div>
        </div>
        <div
          ref={originalScrollRef}
          className="flex-1 overflow-y-auto overflow-x-hidden p-6 bg-gray-50 dark:bg-gray-900 min-h-0"
        >
          {!getFullOriginalText() && (
            <div className="text-center text-muted-foreground py-8">
              等待输入...
            </div>
          )}
          
          {getFullOriginalText() && (
            <p className="text-base font-mono whitespace-pre-wrap break-words leading-relaxed">
              {renderTextWithHighlights(getFullOriginalText(), originalHighlights)}
            </p>
          )}
        </div>
      </div>

      {/* 下半部分：译文区域 */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="bg-muted px-4 py-2 border-b border-border flex-shrink-0 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            译文 ({getLanguageLabel(targetLanguage)})
          </h3>
        </div>
        <div
          ref={translationScrollRef}
          className="flex-1 overflow-y-auto overflow-x-hidden p-6 bg-green-50 dark:bg-green-950 min-h-0"
        >
          {!getFullTranslationText() && (
            <div className="text-center text-muted-foreground py-8">
              等待翻译...
            </div>
          )}
          
          {getFullTranslationText() && (
            <p className="text-base whitespace-pre-wrap break-words leading-relaxed">
              {renderTextWithHighlights(getFullTranslationText(), translationHighlights)}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

