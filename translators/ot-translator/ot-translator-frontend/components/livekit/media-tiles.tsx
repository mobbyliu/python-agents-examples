import React, { useMemo } from 'react';
import { Track } from 'livekit-client';
import { AnimatePresence, motion } from 'motion/react';
import {
  type TrackReference,
  useLocalParticipant,
  useTracks,
  useVoiceAssistant,
} from '@livekit/components-react';
import { cn } from '@/lib/utils';
import { AgentTile } from './agent-tile';
import { AvatarTile } from './avatar-tile';
import { VideoTile } from './video-tile';

const MotionVideoTile = motion.create(VideoTile);
const MotionAgentTile = motion.create(AgentTile);
const MotionAvatarTile = motion.create(AvatarTile);

const animationProps = {
  initial: {
    opacity: 0,
    scale: 0,
  },
  animate: {
    opacity: 1,
    scale: 1,
  },
  exit: {
    opacity: 0,
    scale: 0,
  },
  transition: {
    type: 'spring',
    stiffness: 675,
    damping: 75,
    mass: 1,
  },
};

const classNames = {
  // GRID
  // 2 Columns x 3 Rows
  grid: [
    'h-full w-full',
    'grid gap-x-2 place-content-center',
    'grid-cols-[1fr_1fr] grid-rows-[90px_1fr_90px]',
  ],
  // Agent
  // chatOpen: true,
  // hasSecondTile: true
  // layout: Column 1 / Row 1
  // align: x-end y-center
  agentChatOpenWithSecondTile: ['col-start-1 row-start-1', 'self-center justify-self-end'],
  // Agent
  // chatOpen: true,
  // hasSecondTile: false
  // layout: Column 1 / Row 1 / Column-Span 2
  // align: x-center y-center
  agentChatOpenWithoutSecondTile: ['col-start-1 row-start-1', 'col-span-2', 'place-content-center'],
  // Agent
  // chatOpen: false
  // layout: Column 1 / Row 1 / Column-Span 2 / Row-Span 3
  // align: x-center y-center
  agentChatClosed: ['col-start-1 row-start-1', 'col-span-2 row-span-3', 'place-content-center'],
  // Second tile
  // chatOpen: true,
  // hasSecondTile: true
  // layout: Column 2 / Row 1
  // align: x-start y-center
  secondTileChatOpen: ['col-start-2 row-start-1', 'self-center justify-self-start'],
  // Second tile
  // chatOpen: false,
  // hasSecondTile: false
  // layout: Column 2 / Row 2
  // align: x-end y-end
  secondTileChatClosed: ['col-start-2 row-start-3', 'place-content-end'],
};

export function useLocalTrackRef(source: Track.Source) {
  const { localParticipant } = useLocalParticipant();
  const publication = localParticipant.getTrackPublication(source);
  const trackRef = useMemo<TrackReference | undefined>(
    () => (publication ? { source, participant: localParticipant, publication } : undefined),
    [source, publication, localParticipant]
  );
  return trackRef;
}

interface MediaTilesProps {
  chatOpen: boolean;
}

export function MediaTiles({ chatOpen }: MediaTilesProps) {
  const {
    state: agentState,
    audioTrack: agentAudioTrack,
    videoTrack: agentVideoTrack,
  } = useVoiceAssistant();
  const [screenShareTrack] = useTracks([Track.Source.ScreenShare]);
  const cameraTrack: TrackReference | undefined = useLocalTrackRef(Track.Source.Camera);

  const isCameraEnabled = cameraTrack && !cameraTrack.publication.isMuted;
  const isScreenShareEnabled = screenShareTrack && !screenShareTrack.publication.isMuted;
  const hasSecondTile = isCameraEnabled || isScreenShareEnabled;

  const transition = {
    ...animationProps.transition,
    delay: chatOpen ? 0 : 0.15, // delay on close
  };
  const agentAnimate = {
    ...animationProps.animate,
    scale: chatOpen ? 1 : 3,
    transition,
  };
  const avatarAnimate = {
    ...animationProps.animate,
    transition,
  };
  const agentLayoutTransition = transition;
  const avatarLayoutTransition = transition;

  const isAvatar = agentVideoTrack !== undefined;

  return (
    <div className="pointer-events-none fixed inset-0 z-50">
      {/* Audio Visualizer - Fixed to bottom right corner */}
      <div className="absolute right-4 bottom-16 md:right-8 md:bottom-20">
        <AnimatePresence mode="popLayout">
          {!isAvatar && (
            // audio-only agent - compact size in corner
            <MotionAgentTile
              key="agent"
              layoutId="agent"
              {...animationProps}
              animate={{
                ...animationProps.animate,
                transition: animationProps.transition,
              }}
              transition={agentLayoutTransition}
              state={agentState}
              audioTrack={agentAudioTrack}
              className="h-[60px]"
            />
          )}
          {isAvatar && (
            // avatar agent - compact size in corner
            <MotionAvatarTile
              key="avatar"
              layoutId="avatar"
              {...animationProps}
              animate={{
                ...animationProps.animate,
                transition: animationProps.transition,
              }}
              transition={avatarLayoutTransition}
              videoTrack={agentVideoTrack}
              className="h-[60px] [&>video]:h-[60px] [&>video]:w-auto"
            />
          )}
        </AnimatePresence>
      </div>

      {/* Camera/Screen Share - top right corner */}
      <div className="absolute right-4 top-6 md:right-8 md:top-8">
        <AnimatePresence>
          {cameraTrack && isCameraEnabled && (
            <MotionVideoTile
              key="camera"
              layout="position"
              layoutId="camera"
              {...animationProps}
              trackRef={cameraTrack}
              transition={animationProps.transition}
              className="h-[120px] rounded-lg overflow-hidden shadow-lg"
            />
          )}
          {isScreenShareEnabled && (
            <MotionVideoTile
              key="screen"
              layout="position"
              layoutId="screen"
              {...animationProps}
              trackRef={screenShareTrack}
              transition={animationProps.transition}
              className="h-[120px] rounded-lg overflow-hidden shadow-lg"
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
