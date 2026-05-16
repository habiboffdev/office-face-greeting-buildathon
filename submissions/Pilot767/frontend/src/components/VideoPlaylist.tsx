import { useCallback, useEffect, useRef, useState } from 'react';
import type { Video } from '../services/api';

interface Props {
  videos: Video[];
}

export function VideoPlaylist({ videos }: Props) {
  const [index, setIndex] = useState(0);
  const [fadeNext, setFadeNext] = useState(false);
  const primary = useRef<HTMLVideoElement>(null);
  const secondary = useRef<HTMLVideoElement>(null);
  const frontIsPrimary = useRef(true);

  const count = videos.length;

  const urlAt = useCallback(
    (i: number) => (count ? videos[i % count].url : ''),
    [videos, count],
  );

  const playOn = (el: HTMLVideoElement | null, i: number) => {
    if (!el || !count) return;
    el.src = urlAt(i);
    el.load();
    el.play().catch(() => {});
  };

  useEffect(() => {
    if (!count) return;
    setIndex(0);
    playOn(primary.current, 0);
  }, [videos, count]);

  const goNext = useCallback(() => {
    if (count <= 1) {
      playOn(frontIsPrimary.current ? primary.current : secondary.current, index);
      return;
    }
    const nextIndex = (index + 1) % count;
    const back = frontIsPrimary.current ? secondary.current : primary.current;
    playOn(back, nextIndex);
    setFadeNext(true);
    setTimeout(() => {
      frontIsPrimary.current = !frontIsPrimary.current;
      setIndex(nextIndex);
      setFadeNext(false);
    }, 650);
  }, [index, count, urlAt]);

  const handleEnded = () => goNext();

  if (!count) {
    return (
      <div className="flex h-full items-center justify-center bg-black text-slate-400">
        No videos
      </div>
    );
  }

  /* Ekranni to‘ldirish: kenglik bo‘yicha yon qora chiziqlar bo‘lmaydi (object-cover). */
  const baseVideo =
    'absolute inset-0 h-full w-full object-cover object-center';

  /** Oldingi formulada crossfade dan keyin noto‘g‘ri player ko‘rinardi (video “yarim” to‘xtagandek). */
  const fp = frontIsPrimary.current;
  const primaryOpacity =
    fadeNext ? (fp ? 'opacity-0' : 'opacity-100') : fp ? 'opacity-100' : 'opacity-0';
  const secondaryOpacity =
    fadeNext ? (fp ? 'opacity-100' : 'opacity-0') : fp ? 'opacity-0' : 'opacity-100';

  return (
    <div className="relative h-full min-h-0 w-full overflow-hidden bg-black">
      <video
        ref={primary}
        className={`${baseVideo} transition-opacity duration-700 ease-in-out ${primaryOpacity}`}
        muted
        playsInline
        autoPlay
        onEnded={!fadeNext && fp ? handleEnded : undefined}
      />
      <video
        ref={secondary}
        className={`${baseVideo} transition-opacity duration-700 ease-in-out ${secondaryOpacity}`}
        muted
        playsInline
        autoPlay
        onEnded={!fadeNext && !fp ? handleEnded : undefined}
      />
    </div>
  );
}
