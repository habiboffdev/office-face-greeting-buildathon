import * as faceapi from "face-api.js";

let modelsLoaded = false;
let loadingPromise: Promise<void> | null = null;

export async function loadFaceModels() {
  if (modelsLoaded) return;
  if (loadingPromise) return loadingPromise;
  loadingPromise = (async () => {
    console.log("[FaceAPI] Loading TinyFaceDetector, Landmarks, Recognition, Expressions...");
    const url = "/models";
    await Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(url),
      faceapi.nets.faceLandmark68Net.loadFromUri(url),
      faceapi.nets.faceRecognitionNet.loadFromUri(url),
      faceapi.nets.faceExpressionNet.loadFromUri(url),
    ]);
    console.log("[FaceAPI] Models loaded successfully.");
    modelsLoaded = true;
  })();
  return loadingPromise;
}

export async function detectAndDescribe(input: HTMLVideoElement | HTMLImageElement | HTMLCanvasElement) {
  // Increased inputSize for better distant face recognition
  const opts = new faceapi.TinyFaceDetectorOptions({ inputSize: 512, scoreThreshold: 0.4 });
  const results = await faceapi
    .detectAllFaces(input, opts)
    .withFaceLandmarks()
    .withFaceExpressions()
    .withFaceDescriptors();
  return results;
}

export function euclidean(a: Float32Array | number[], b: Float32Array | number[]) {
  let s = 0;
  for (let i = 0; i < a.length; i++) {
    const d = (a[i] as number) - (b[i] as number);
    s += d * d;
  }
  return Math.sqrt(s);
}

/** Compare a candidate descriptor to a person's stored embeddings. Returns the smallest distance. */
export function bestDistance(candidate: Float32Array | number[], embeddings: number[][]) {
  let min = Infinity;
  for (const e of embeddings) {
    const d = euclidean(candidate, e);
    if (d < min) min = d;
  }
  return min;
}

/** Map euclidean distance (~0.3 strong .. 0.6 weak) to confidence 0..1. */
export function distanceToConfidence(d: number) {
  // 0.3 -> ~0.95, 0.45 -> ~0.7, 0.6 -> ~0.4
  return Math.max(0, Math.min(1, 1 - d));
}

export const MATCH_THRESHOLD = 0.55; // distance threshold; below = match
