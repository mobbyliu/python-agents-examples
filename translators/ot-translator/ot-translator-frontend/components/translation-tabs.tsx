'use client';

import { cn } from '@/lib/utils';

export type DisplayMode = 'alternate' | 'split';

interface TranslationTabsProps {
  currentMode: DisplayMode;
  onModeChange: (mode: DisplayMode) => void;
  className?: string;
}

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

export function TranslationTabs({
  currentMode,
  onModeChange,
  className,
}: TranslationTabsProps) {
  return (
    <div
      className={cn(
        'hidden lg:flex flex-col gap-2 p-3 bg-muted/50 border-r border-border',
        className
      )}
    >
      <div className="text-xs font-semibold text-muted-foreground px-2 mb-1">
        显示模式
      </div>
      
      {tabOptions.map((option) => (
        <button
          key={option.id}
          onClick={() => onModeChange(option.id)}
          className={cn(
            'flex flex-col items-start gap-1 px-3 py-3 rounded-lg transition-all duration-200',
            'hover:bg-accent hover:text-accent-foreground',
            'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
            currentMode === option.id
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
              currentMode === option.id ? 'text-muted-foreground' : 'text-muted-foreground/70'
            )}
          >
            {option.description}
          </span>
        </button>
      ))}
    </div>
  );
}

