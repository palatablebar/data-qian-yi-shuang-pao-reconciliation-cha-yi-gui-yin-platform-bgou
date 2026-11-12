/** 批次轮询：running 状态每 2s 拉一次详情，completed/failed 自动停。 */
import { useEffect, useRef, useState } from 'react';
import { getBatch } from '../api/batches';
import type { Batch } from '../types/models';

export function useBatchPolling(batchId: number | null, initial: Batch | null): {
  batch: Batch | null;
  reload: () => void;
  polling: boolean;
} {
  const [batch, setBatch] = useState<Batch | null>(initial);
  const [polling, setPolling] = useState(false);
  const timer = useRef<number | null>(null);

  const reload = () => {
    if (batchId === null) return;
    getBatch(batchId)
      .then((next) => setBatch(next))
      .catch(() => undefined);
  };

  useEffect(() => {
    if (batchId === null) return;
    let alive = true;
    const tick = async () => {
      try {
        const next = await getBatch(batchId);
        if (!alive) return;
        setBatch(next);
        const shouldPoll = next.status === 'running' || next.status === 'pending';
        setPolling(shouldPoll);
        if (shouldPoll) {
          timer.current = window.setTimeout(tick, 2000);
        }
      } catch {
        if (alive) timer.current = window.setTimeout(tick, 4000);
      }
    };
    tick();
    return () => {
      alive = false;
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [batchId]);

  return { batch, reload, polling };
}
