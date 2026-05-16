import { useState, useRef, useEffect } from "react";

export default function VideoPlayer({ videos, paused }) {
  const videoRef = useRef(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [hasVideos, setHasVideos] = useState(false);

  useEffect(() => {
    setHasVideos(videos && videos.length > 0);
  }, [videos]);

  const handleEnded = () => {
    if (!videos || videos.length === 0) return;
    setCurrentIndex((prev) => (prev + 1) % videos.length);
  };

  useEffect(() => {
    if (videoRef.current && hasVideos) {
      videoRef.current.load();
      videoRef.current.play().catch(() => {});
    }
  }, [currentIndex, hasVideos]);

  useEffect(() => {
    if (!videoRef.current) return;
    if (paused) videoRef.current.pause();
    else videoRef.current.play().catch(() => {});
  }, [paused]);

  if (!hasVideos) {
    return (
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
        <div className="text-center opacity-30">
          <div className="w-20 h-20 border-2 border-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <div className="w-0 h-0 border-t-8 border-b-8 border-l-12 border-transparent border-l-white/40 ml-1" />
          </div>
          <p className="text-white/40 text-sm font-body">No videos in playlist</p>
          <p className="text-white/20 text-xs mt-1">Add videos from Admin Panel</p>
        </div>
      </div>
    );
  }

  return (
    <video
      ref={videoRef}
      className="absolute inset-0 w-full h-full object-cover"
      autoPlay
      muted
      playsInline
      onEnded={handleEnded}
      key={currentIndex}
    >
      <source src={videos[currentIndex]?.video_url} />
    </video>
  );
}