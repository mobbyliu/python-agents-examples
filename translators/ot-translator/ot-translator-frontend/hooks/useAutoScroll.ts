import { useEffect, RefObject } from 'react';

export function useAutoScroll(
  scrollRef: RefObject<HTMLDivElement | null>,
  dependencies: any[]
) {
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, dependencies);
}

