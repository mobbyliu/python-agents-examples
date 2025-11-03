'use client';

import { toastAlert } from '@/components/alert-toast';
import { AgentControlBar } from '@/components/livekit/agent-control-bar/agent-control-bar';
import { ChatEntry } from '@/components/livekit/chat/chat-entry';
import { ChatMessageView } from '@/components/livekit/chat/chat-message-view';
import { MediaTiles } from '@/components/livekit/media-tiles';
import { TranslationAlternate } from '@/components/translation-alternate';
import { TranslationSplit } from '@/components/translation-split';
import useChatAndTranscription from '@/hooks/useChatAndTranscription';
import { useDebugMode } from '@/hooks/useDebug';
import useTextStreamLogger from '@/hooks/useTextStreamLogger';
import { cn } from '@/lib/utils';
import {
  type AgentState,
  type ReceivedChatMessage,
  useRoomContext,
  useVoiceAssistant,
} from '@livekit/components-react';
import { AnimatePresence, motion } from 'motion/react';
import React, { useEffect, useState } from 'react';

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

// Display Mode Types
type DisplayMode = 'alternate' | 'split';

interface TabOption {
  id: DisplayMode;
  label: string;
  description: string;
  icon: string;
}

const tabOptions: TabOption[] = [
  {
    id: 'alternate',
    label: '交替显示',
    description: '原文与译文交替显示',
    icon: '📝',
  },
  {
    id: 'split',
    label: '分屏显示',
    description: '上下分屏对照',
    icon: '⬍',
  },
];

function isAgentAvailable(agentState: AgentState) {
  return agentState == 'listening' || agentState == 'thinking' || agentState == 'speaking';
}

interface SessionViewProps {
  disabled: boolean;
  capabilities: {
    supportsChatInput: boolean;
    supportsVideoInput: boolean;
    supportsScreenShare: boolean;
  };
  sessionStarted: boolean;
}

export const SessionView = ({
  disabled,
  capabilities,
  sessionStarted,
  ref,
}: React.ComponentProps<'div'> & SessionViewProps) => {
  const { state: agentState } = useVoiceAssistant();
  const [chatOpen, setChatOpen] = useState(false);
  const [displayMode, setDisplayMode] = useState<DisplayMode>('alternate');
  const { messages, send } = useChatAndTranscription();
  const room = useRoomContext();

  // 翻译配置状态
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
  const [showConfig, setShowConfig] = useState<boolean>(false);

  useDebugMode();
  useTextStreamLogger();

  async function handleSendMessage(message: string) {
    await send(message);
  }

  // 获取语言标签
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

      // 发送配置到后端（防抖配置由后端环境变量控制）
      const payload = {
        source: sourceLanguage,
        target: targetLanguage,
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

  useEffect(() => {
    if (sessionStarted) {
      const timeout = setTimeout(() => {
        if (!isAgentAvailable(agentState)) {
          const reason =
            agentState === 'connecting'
              ? 'Agent did not join the room. '
              : 'Agent connected but did not complete initializing. ';

          toastAlert({
            title: 'Session ended',
            description: (
              <p className="w-full">
                {reason}
                <a
                  target="_blank"
                  rel="noopener noreferrer"
                  href="https://docs.livekit.io/agents/start/voice-ai/"
                  className="whitespace-nowrap underline"
                >
                  See quickstart guide
                </a>
                .
              </p>
            ),
          });
          room.disconnect();
        }
      }, 10_000);

      return () => clearTimeout(timeout);
    }
  }, [agentState, sessionStarted, room]);

  return (
    <main
      ref={ref}
      inert={disabled}
      className={
        // prevent page scrollbar
        // when !chatOpen due to 'translate-y-20'
        cn(!chatOpen && 'max-h-svh overflow-hidden')
      }
    >
      <ChatMessageView
        className={cn(
          'mx-auto min-h-svh w-full max-w-2xl px-3 pt-20 pb-32 transition-[opacity,translate] duration-300 ease-out md:px-0 md:pt-24 md:pb-36',
          chatOpen ? 'translate-y-0 opacity-100 delay-200' : 'translate-y-20 opacity-0'
        )}
      >
        <div className="space-y-3 whitespace-pre-wrap">
          <AnimatePresence>
            {messages.map((message: ReceivedChatMessage) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 1, height: 'auto', translateY: 0.001 }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              >
                <ChatEntry hideName key={message.id} entry={message} />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </ChatMessageView>

      <div className="bg-background fixed top-0 right-0 left-0 h-0">
        {/* skrim */}
        <div className="from-background absolute bottom-0 left-0 h-8 w-full translate-y-full bg-gradient-to-b to-transparent" />
      </div>

      {/* Translation Display - With Tab Navigation */}
      {sessionStarted && (
        <div className="fixed inset-4 top-4 bottom-20 md:inset-6 md:top-6 md:bottom-24 flex z-30 bg-background/80 backdrop-blur-sm border border-border rounded-lg overflow-hidden shadow-lg">
          {/* Left Tab Navigation */}
          <div className="hidden lg:flex flex-col gap-2 p-3 bg-muted/50 border-r border-border w-40 flex-shrink-0">
            <div className="text-xs font-semibold text-muted-foreground px-2 mb-1">
              显示模式
            </div>
            
            {tabOptions.map((option) => (
              <button
                key={option.id}
                onClick={() => setDisplayMode(option.id)}
                className={cn(
                  'flex flex-col items-start gap-1 px-3 py-3 rounded-lg transition-all duration-200',
                  'hover:bg-accent hover:text-accent-foreground',
                  'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
                  displayMode === option.id
                    ? 'bg-background text-foreground shadow-sm border border-border'
                    : 'bg-transparent text-muted-foreground'
                )}
              >
                <div className="flex items-center gap-2 w-full">
                  <span className="text-lg">{option.icon}</span>
                  <span className="text-sm font-medium">{option.label}</span>
                </div>
                <span
                  className={cn(
                    'text-xs',
                    displayMode === option.id ? 'text-muted-foreground' : 'text-muted-foreground/70'
                  )}
                >
                  {option.description}
                </span>
              </button>
            ))}
          </div>
          
          {/* Main Content Area with Config Header */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Configuration Header */}
            <div className="bg-muted/50 border-b border-border px-4 py-2 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground">翻译配置:</span>
                <span className="text-sm font-medium">
                  {getLanguageLabel(sourceLanguage)} → {getLanguageLabel(targetLanguage)}
                </span>
              </div>
              <button
                onClick={() => setShowConfig(!showConfig)}
                className="px-3 py-1 text-sm text-muted-foreground hover:text-foreground hover:bg-background rounded transition-colors flex items-center gap-1"
                title="翻译配置"
              >
                ⚙️ 配置
              </button>
            </div>

            {/* Configuration Panel (Expandable) */}
            {showConfig && (
              <div className="bg-muted border-b border-border p-4 flex-shrink-0">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">翻译配置</h3>
                  <button
                    onClick={() => setShowConfig(false)}
                    className="text-muted-foreground hover:text-foreground text-sm"
                  >
                    ✕
                  </button>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                </div>
                
                <div className="text-xs text-muted-foreground mt-2">
                  💡 防抖延迟和译文防抖设置由后端环境变量控制
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
            )}

            {/* Translation Content */}
            <div className="flex-1 overflow-hidden">
              {displayMode === 'alternate' && (
                <TranslationAlternate 
                  className="h-full"
                  sourceLanguage={sourceLanguage}
                  targetLanguage={targetLanguage}
                  getLanguageLabel={getLanguageLabel}
                />
              )}
              {displayMode === 'split' && (
                <TranslationSplit 
                  className="h-full"
                  sourceLanguage={sourceLanguage}
                  targetLanguage={targetLanguage}
                  getLanguageLabel={getLanguageLabel}
                />
              )}
            </div>
          </div>
        </div>
      )}

      <MediaTiles chatOpen={chatOpen} />

      <div className="bg-background fixed right-0 bottom-0 left-0 z-50 px-3 pt-2 pb-3 md:px-12 md:pb-12">
        <motion.div
          key="control-bar"
          initial={{ opacity: 0, translateY: '100%' }}
          animate={{
            opacity: sessionStarted ? 1 : 0,
            translateY: sessionStarted ? '0%' : '100%',
          }}
          transition={{ duration: 0.3, delay: sessionStarted ? 0.5 : 0, ease: 'easeOut' }}
        >
          <div className="relative z-10 mx-auto w-full max-w-2xl">
            <AgentControlBar
              capabilities={capabilities}
              onChatOpenChange={setChatOpen}
              onSendMessage={handleSendMessage}
            />
          </div>
          {/* skrim */}
          <div className="from-background border-background absolute top-0 left-0 h-12 w-full -translate-y-full bg-gradient-to-t to-transparent" />
        </motion.div>
      </div>
    </main>
  );
};
