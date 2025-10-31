import { type AgentState, BarVisualizer, type TrackReference } from '@livekit/components-react';
import { cn } from '@/lib/utils';

interface AgentAudioTileProps {
  state: AgentState;
  audioTrack: TrackReference;
  className?: string;
}

export const AgentTile = ({
  state,
  audioTrack,
  className,
  ref,
}: React.ComponentProps<'div'> & AgentAudioTileProps) => {
  return (
    <div ref={ref} className={cn(className)}>
      <BarVisualizer
        barCount={5}
        state={state}
        options={{ minHeight: 3 }}
        trackRef={audioTrack}
        className={cn('flex w-24 items-center justify-center gap-0.5 bg-background/80 backdrop-blur-sm rounded-full px-3 py-2 shadow-lg border border-border')}
      >
        <span
          className={cn([
            'bg-muted min-h-2 w-2 rounded-full',
            'origin-center transition-colors duration-250 ease-linear',
            'data-[lk-highlighted=true]:bg-foreground data-[lk-muted=true]:bg-muted',
          ])}
        />
      </BarVisualizer>
    </div>
  );
};
