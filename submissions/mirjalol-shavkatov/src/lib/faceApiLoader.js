// Singleton loader for face-api.js
// Models hosted on a working CDN path

const MODEL_URL = "https://vladmandic.github.io/face-api/model";

let loadPromise = null;

export function loadFaceApi() {
  if (loadPromise) return loadPromise;

  loadPromise = new Promise((resolve, reject) => {
    // If already loaded
    if (window.faceapi && window.faceapi.nets?.tinyFaceDetector?.isLoaded) {
      return resolve(window.faceapi);
    }

    const scriptLoaded = window.faceapi ? Promise.resolve() : new Promise((res, rej) => {
      const existing = document.querySelector('script[data-faceapi]');
      if (existing) { existing.addEventListener('load', res); return; }
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js";
      script.setAttribute("data-faceapi", "true");
      script.onload = res;
      script.onerror = rej;
      document.head.appendChild(script);
    });

    scriptLoaded.then(async () => {
      const faceapi = window.faceapi;
      if (!faceapi) { reject(new Error("faceapi not on window")); return; }

      try {
        await Promise.all([
          faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
          faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
          faceapi.nets.faceLandmark68TinyNet.loadFromUri(MODEL_URL),
        ]);
        resolve(faceapi);
      } catch (err) {
        loadPromise = null; // allow retry
        reject(err);
      }
    }).catch((err) => {
      loadPromise = null;
      reject(err);
    });
  });

  return loadPromise;
}