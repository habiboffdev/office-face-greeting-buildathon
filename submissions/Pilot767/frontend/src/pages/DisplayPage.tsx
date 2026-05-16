import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { VideoPlaylist } from '../components/VideoPlaylist';
import { WelcomeOverlay, type WelcomeContent } from '../components/WelcomeOverlay';
import { useDisplayWebSocket } from '../hooks/useWebSocket';
import { fetchVideos, type Video, type WelcomePayload } from '../services/api';

const OVERLAY_MS = 5000;
const BIRTHDAY_OVERLAY_MS = 10000;

function durationFor(w: WelcomeContent): number {
  if (w.isBirthday) return BIRTHDAY_OVERLAY_MS;
  return OVERLAY_MS;
}

function payloadToWelcome(data: WelcomePayload, welcomeSeq: number): WelcomeContent {
  return {
    title: data.greeting,
    subtitle: data.subtitle || 'Rocusga xush kelibsiz!',
    isVip: data.is_vip,
    isBirthday: data.is_birthday,
    isFounder: data.is_founder,
    founderImageUrl: data.founder_image_url,
    founderVisitsToday: data.founder_visits_today,
    visitsToday: data.visits_today,
    personId: data.person_id,
    welcomeSeq,
  };
}

export function DisplayPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [welcome, setWelcome] = useState<WelcomeContent | null>(null);

  const welcomeRef = useRef<WelcomeContent | null>(null);
  const queueRef = useRef<WelcomeContent[]>([]);
  const hideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const welcomeSeqRef = useRef(0);

  const clearHideTimer = () => {
    if (hideTimeoutRef.current !== null) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
  };

  const armDismissRef = useRef<(content: WelcomeContent) => void>(() => {});

  armDismissRef.current = (content: WelcomeContent) => {
    clearHideTimer();
    hideTimeoutRef.current = setTimeout(() => {
      hideTimeoutRef.current = null;
      const next = queueRef.current.shift() ?? null;
      if (next) {
        welcomeRef.current = next;
        setWelcome(next);
        armDismissRef.current(next);
      } else {
        welcomeRef.current = null;
        setWelcome(null);
      }
    }, durationFor(content));
  };

  const onWelcome = useCallback((data: WelcomePayload) => {
    const content = payloadToWelcome(data, ++welcomeSeqRef.current);
    const cur = welcomeRef.current;

    // Hozir aynan shu odamning tabrigi chiqyapti — qayta yuborilganda navbatni to'ldirmaymiz
    if (cur?.personId === content.personId) return;

    if (!cur) {
      welcomeRef.current = content;
      setWelcome(content);
      armDismissRef.current(content);
    } else {
      // Navbat cheklanmaydi: 2, 3, 10 ta odam — bari birma-bir chiqadi
      queueRef.current.push(content);
    }
  }, []);

  useDisplayWebSocket(onWelcome);

  useEffect(() => {
    return () => clearHideTimer();
  }, []);

  useEffect(() => {
    fetchVideos().then(setVideos).catch(console.error);
  }, []);

  return (
    <div className="relative h-[100dvh] min-h-0 w-full overflow-hidden bg-black">
      <VideoPlaylist videos={videos} />
      <WelcomeOverlay welcome={welcome} />

      <Link
        to="/admin"
        className="absolute bottom-4 right-4 z-30 rounded-lg border border-white/10 bg-black/30 px-3 py-1 text-xs text-slate-500 opacity-0 transition hover:opacity-100"
      >
        Admin
      </Link>
    </div>
  );
}
