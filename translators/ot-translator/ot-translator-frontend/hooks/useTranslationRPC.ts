import { TranslationData } from '@/lib/types';
import { useMaybeRoomContext } from '@livekit/components-react';
import { RpcInvocationData } from 'livekit-client';
import { useEffect } from 'react';

export function useTranslationRPC(
  onTranslationReceived: (payload: TranslationData) => void
) {
  const room = useMaybeRoomContext();

  useEffect(() => {
    if (!room || !room.localParticipant) return;

    const handleReceiveTranslation = async (
      rpcInvocation: RpcInvocationData
    ): Promise<string> => {
      try {
        const payload = JSON.parse(rpcInvocation.payload) as TranslationData;

        if (payload && payload.original) {
          onTranslationReceived(payload);
          return 'Success: Translation received';
        } else {
          return 'Error: Invalid translation data format';
        }
      } catch (error) {
        console.error('Error processing translation RPC:', error);
        return 'Error: ' + (error instanceof Error ? error.message : String(error));
      }
    };

    room.localParticipant.registerRpcMethod('receive_translation', handleReceiveTranslation);

    return () => {
      if (room && room.localParticipant) {
        room.localParticipant.unregisterRpcMethod('receive_translation');
      }
    };
  }, [room, onTranslationReceived]);
}

