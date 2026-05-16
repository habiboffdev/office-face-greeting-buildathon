/** JPEG data URL (~small) for admin thumbnails; used as `PlaylistItem.poster`. */
export async function captureVideoPosterDataUrl(file: File, maxEdge = 640): Promise<string | null> {
  return new Promise((resolve) => {
    const vid = document.createElement("video");
    vid.muted = true;
    vid.playsInline = true;
    vid.preload = "auto";
    const url = URL.createObjectURL(file);

    const cleanup = () => {
      URL.revokeObjectURL(url);
      vid.src = "";
    };

    const fail = () => {
      cleanup();
      resolve(null);
    };

    const t = window.setTimeout(fail, 12_000);

    vid.onloadeddata = () => {
      try {
        const target = Math.min(0.75, (vid.duration || 2) * 0.05);
        vid.currentTime = Number.isFinite(target) && target > 0 ? target : 0.1;
      } catch {
        vid.currentTime = 0.1;
      }
    };

    vid.onseeked = () => {
      try {
        const w = vid.videoWidth || 320;
        const h = vid.videoHeight || 240;
        const scale = Math.min(1, maxEdge / Math.max(w, h));
        const cw = Math.max(1, Math.round(w * scale));
        const ch = Math.max(1, Math.round(h * scale));
        const canvas = document.createElement("canvas");
        canvas.width = cw;
        canvas.height = ch;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          window.clearTimeout(t);
          fail();
          return;
        }
        ctx.drawImage(vid, 0, 0, cw, ch);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.72);
        window.clearTimeout(t);
        cleanup();
        resolve(dataUrl);
      } catch {
        window.clearTimeout(t);
        fail();
      }
    };

    vid.onerror = fail;
    vid.src = url;
    void vid.load();
  });
}
