import { useEffect, useRef, useState } from 'react';

interface UseTypewriterOptions {
  speed?: number; // 每个单位的延迟时间（毫秒）
  mode?: 'character' | 'word'; // 打字模式：逐字符或逐词
  onComplete?: () => void; // 打字完成的回调
}

/**
 * 打字机效果 Hook
 * 支持逐字符或逐词显示文本
 */
export function useTypewriter(
  text: string,
  options: UseTypewriterOptions = {}
): {
  displayedText: string;
  isTyping: boolean;
  skip: () => void;
  reset: () => void;
} {
  const { speed = 30, mode = 'character', onComplete } = options;
  const [displayedText, setDisplayedText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const textRef = useRef(text);
  const modeRef = useRef(mode);

  // 将文本分词（用于逐词模式）
  const getWords = (str: string): string[] => {
    if (!str) return [];
    // 匹配中文字符、英文单词、数字、标点等
    const regex = /[\u4e00-\u9fa5]|[a-zA-Z]+|[0-9]+|[^\u4e00-\u9fa5a-zA-Z0-9\s]+|\s+/g;
    return str.match(regex) || [];
  };

  // 更新文本或模式时重置
  useEffect(() => {
    if (textRef.current !== text || modeRef.current !== mode) {
      textRef.current = text;
      modeRef.current = mode;
      setCurrentIndex(0);
      setDisplayedText('');
      setIsTyping(true);
    }
  }, [text, mode]);

  // 打字机逻辑
  useEffect(() => {
    if (!isTyping) return;

    if (mode === 'character') {
      // 逐字符模式
      if (currentIndex >= text.length) {
        setIsTyping(false);
        onComplete?.();
        return;
      }

      timerRef.current = setTimeout(() => {
        setDisplayedText(text.slice(0, currentIndex + 1));
        setCurrentIndex((prev) => prev + 1);
      }, speed);
    } else {
      // 逐词模式
      const words = getWords(text);
      if (currentIndex >= words.length) {
        setIsTyping(false);
        onComplete?.();
        return;
      }

      timerRef.current = setTimeout(() => {
        const displayWords = words.slice(0, currentIndex + 1).join('');
        setDisplayedText(displayWords);
        setCurrentIndex((prev) => prev + 1);
      }, speed);
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [currentIndex, text, speed, mode, isTyping, onComplete]);

  // 跳过动画，直接显示全部文本
  const skip = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    setDisplayedText(text);
    setCurrentIndex(text.length);
    setIsTyping(false);
    onComplete?.();
  };

  // 重置
  const reset = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    setDisplayedText('');
    setCurrentIndex(0);
    setIsTyping(text.length > 0);
    textRef.current = text;
    modeRef.current = mode;
  };

  return {
    displayedText,
    isTyping,
    skip,
    reset,
  };
}

