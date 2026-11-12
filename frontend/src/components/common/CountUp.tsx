/** 数字滚动：指数缓动，只在值变化时播放（对账完成后“落账”感）。 */
import { useEffect, useRef, useState } from 'react';

interface Props {
  value: number;
  digits?: number;
  suffix?: string;
  duration?: number;
}

const easeOutExpo = (t: number): number => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

export function CountUp({ value, digits = 0, suffix = '', duration = 900 }: Props) {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    const from = fromRef.current;
    const started = performance.now();
    if (frameRef.current) cancelAnimationFrame(frameRef.current);

    const tick = (now: number) => {
      const progress = Math.min(1, (now - started) / duration);
      const next = from + (value - from) * easeOutExpo(progress);
      setDisplay(next);
      if (progress < 1) frameRef.current = requestAnimationFrame(tick);
      else {
        fromRef.current = value;
        setDisplay(value);
      }
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [value, duration]);

  return (
    <span>
      {display.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}
      {suffix}
    </span>
  );
}
