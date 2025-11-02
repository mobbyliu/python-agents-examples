'use client';

import { useAutoScroll } from '@/hooks/useAutoScroll';
import { useTranslationRPC } from '@/hooks/useTranslationRPC';
import { TranslationData } from '@/lib/types';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface TranslationSplitProps {
  className?: string;
  sourceLanguage: string;
  targetLanguage: string;
  getLanguageLabel: (lang: string) => string;
}

type ChangeType = 'same' | 'added' | 'modified';

interface TextChange {
  type: ChangeType;
  text: string;
  startIndex: number;
}

export function TranslationSplit({ 
  className, 
  sourceLanguage, 
  targetLanguage, 
  getLanguageLabel 
}: TranslationSplitProps) {
  // 原文区域状态
  const [accumulatedOriginal, setAccumulatedOriginal] = useState<string>('');
  const [currentOriginal, setCurrentOriginal] = useState<string>('');
  const [prevOriginal, setPrevOriginal] = useState<string>('');
  const [currentLanguage, setCurrentLanguage] = useState<string>('');
  
  // 译文区域状态
  const [accumulatedTranslation, setAccumulatedTranslation] = useState<string>('');
  const [currentTranslation, setCurrentTranslation] = useState<string>('');
  const [prevTranslation, setPrevTranslation] = useState<string>('');

  const currentOriginalRef = useRef(currentOriginal);
  const currentTranslationRef = useRef(currentTranslation);
  
  const originalScrollRef = useRef<HTMLDivElement>(null);
  const translationScrollRef = useRef<HTMLDivElement>(null);

  // 同步 refs
  useEffect(() => {
    currentOriginalRef.current = currentOriginal;
    currentTranslationRef.current = currentTranslation;
  }, [currentOriginal, currentTranslation]);

  // 处理翻译数据
  const handleTranslation = useCallback((payload: TranslationData) => {
    // 原文处理
    if (payload.type === 'interim') {
      const newOriginal = payload.original.text;
      setPrevOriginal(currentOriginalRef.current);
      setCurrentOriginal(newOriginal);
      currentOriginalRef.current = newOriginal;
      setCurrentLanguage(payload.original.language);
    } else if (payload.type === 'final') {
      const newOriginal = payload.original.text;
      setPrevOriginal(currentOriginalRef.current);
      setCurrentOriginal(newOriginal);
      currentOriginalRef.current = newOriginal;

      setAccumulatedOriginal((prev) => {
        const separator = prev ? '\n\n' : '';
        return prev + separator + newOriginal;
      });

      setCurrentLanguage(payload.original.language);
    }

    // 译文处理
    if (payload.translation) {
      const newTranslation = payload.translation.text;

      if (payload.type === 'interim') {
        setPrevTranslation(currentTranslationRef.current);
        setCurrentTranslation(newTranslation);
        currentTranslationRef.current = newTranslation;
      } else if (payload.type === 'final') {
        setPrevTranslation(currentTranslationRef.current);
        setCurrentTranslation(newTranslation);
        currentTranslationRef.current = newTranslation;

        setAccumulatedTranslation((prev) => {
          const separator = prev ? '\n\n' : '';
          return prev + separator + newTranslation;
        });
      }
    }
  }, []);

  // 使用 RPC hook
  useTranslationRPC(handleTranslation);

  // 自动滚动
  useAutoScroll(originalScrollRef, [accumulatedOriginal, currentOriginal]);
  useAutoScroll(translationScrollRef, [accumulatedTranslation, currentTranslation]);

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

  // 获取完整显示文本（累积的历史 + 当前句子）
  const getFullText = (accumulated: string, current: string): string => {
    if (!accumulated && !current) return '';
    if (!accumulated) return current;
    
    const sentences = accumulated.split('\n\n');
    const completedSentences = sentences.slice(0, -1).join('\n\n');
    
    if (completedSentences) {
      return completedSentences + '\n\n' + current;
    }
    return current;
  };

  const fullOriginalText = getFullText(accumulatedOriginal, currentOriginal);
  const fullTranslationText = getFullText(accumulatedTranslation, currentTranslation);

  return (
    <div className={`flex flex-col h-full ${className || ''}`}>
      {/* 上半部分：原文区域 */}
      <div className="flex-1 flex flex-col border-b-2 border-border min-h-0">
        <div className="bg-muted px-4 py-2 border-b border-border flex-shrink-0">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            原文
            {currentLanguage && (
              <span className="text-xs text-muted-foreground">({getLanguageLabel(currentLanguage)})</span>
            )}
          </h3>
        </div>
        <div
          ref={originalScrollRef}
          className="flex-1 overflow-y-auto overflow-x-hidden p-6 bg-gray-50 dark:bg-gray-900 min-h-0"
        >
          {!fullOriginalText && (
            <div className="text-center text-muted-foreground py-8">
              等待输入...
            </div>
          )}
          
          {fullOriginalText && (
            <p className="text-base font-mono whitespace-pre-wrap break-words leading-relaxed">
              {renderTextWithAnimation(
                fullOriginalText, 
                fullOriginalText.slice(0, -currentOriginal.length) + prevOriginal
              )}
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
          {!fullTranslationText && (
            <div className="text-center text-muted-foreground py-8">
              等待翻译...
            </div>
          )}
          
          {fullTranslationText && (
            <p className="text-base whitespace-pre-wrap break-words leading-relaxed">
              {renderTextWithAnimation(
                fullTranslationText, 
                fullTranslationText.slice(0, -currentTranslation.length) + prevTranslation
              )}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
