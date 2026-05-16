import { useEffect, useRef, useState, useCallback } from "react";
import { loadFaceApi } from "@/lib/faceApiLoader";

function euclideanDistance(a, b) {
  if (!a || !b || a.length !== b.length) return Infinity;
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += (a[i] - b[i]) ** 2;
  return Math.sqrt(sum);
}

export default function FaceScanner({ employees, onPersonRecognized, debug = false, cameraIndex = 0 }) {
  const videoRef = useRef(null);
  const overlayCanvasRef = useRef(null);
  const faceApiRef = useRef(null);
  const intervalRef = useRef(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [cameraError, setCameraError] = useState(false);
  const [status, setStatus] = useState("Initializing...");
  const [availableCameras, setAvailableCameras] = useState([]);

  // Debug state
  const [debugInfo, setDebugInfo] = useState(null);
  // { facesDetected, bestMatch: { name, photo_url, distance }, descriptor }

  const employeesWithDescriptors = employees.filter(
    (e) => e.face_descriptor && e.face_descriptor.length > 0
  );

  const loadFaceApiModels = useCallback(async () => {
    if (faceApiRef.current) return;
    try {
      setStatus("Loading face models...");
      const faceapi = await loadFaceApi();
      faceApiRef.current = faceapi;
      setIsLoaded(true);
      setStatus("Camera active");
    } catch (err) {
      console.error("Face API load error:", err);
      setStatus("Model load failed");
    }
  }, []);

  const startCamera = useCallback(async () => {
    try {
      // Get list of available video devices
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter(d => d.kind === 'videoinput');
      setAvailableCameras(videoDevices);

      const deviceId = videoDevices.length > cameraIndex ? videoDevices[cameraIndex].deviceId : undefined;
      const constraints = {
        video: { 
          width: 640, 
          height: 480, 
          facingMode: "user",
          ...(deviceId && { deviceId })
        }
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraError(false);
    } catch (err) {
      console.error("Camera error:", err);
      setCameraError(true);
      setStatus("Camera unavailable");
    }
  }, [cameraIndex]);

  const detectFaces = useCallback(async () => {
    const faceapi = faceApiRef.current;
    const video = videoRef.current;
    if (!faceapi || !video || video.paused || video.ended || !isLoaded) return;

    try {
      const detections = await faceapi
        .detectAllFaces(video, new faceapi.TinyFaceDetectorOptions({ scoreThreshold: 0.4, inputSize: 416 }))
        .withFaceLandmarks(true)
        .withFaceDescriptors();

      // Draw boxes on overlay canvas if debug mode
      if (debug && overlayCanvasRef.current && video.videoWidth) {
        const canvas = overlayCanvasRef.current;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        // Mirror to match video (which is mirrored via CSS)
        ctx.save();
        ctx.scale(-1, 1);
        ctx.translate(-canvas.width, 0);
        detections.forEach((d) => {
          const box = d.detection.box;
          ctx.strokeStyle = "#00ff88";
          ctx.lineWidth = 2;
          ctx.strokeRect(box.x, box.y, box.width, box.height);
          ctx.fillStyle = "#00ff88";
          ctx.font = "14px monospace";
          ctx.fillText(`${(d.detection.score * 100).toFixed(0)}%`, box.x, box.y - 6);
        });
        ctx.restore();
      }

      if (!detections || detections.length === 0) {
        if (debug) setDebugInfo((p) => ({ ...p, facesDetected: 0, bestMatch: null }));
        return;
      }

      if (debug) setDebugInfo((p) => ({ ...p, facesDetected: detections.length }));

      if (employeesWithDescriptors.length === 0) return;

      for (const detection of detections) {
        const descriptor = Array.from(detection.descriptor);
        let bestMatch = null;
        let bestDistance = Infinity;

        for (const employee of employeesWithDescriptors) {
          const dist = euclideanDistance(descriptor, employee.face_descriptor);
          if (dist < bestDistance) {
            bestDistance = dist;
            bestMatch = employee;
          }
        }

        if (debug) {
          setDebugInfo({
            facesDetected: detections.length,
            bestMatch: bestMatch ? { name: bestMatch.name, photo_url: bestMatch.photo_url, distance: bestDistance } : null,
            threshold: 0.5,
            matched: bestMatch && bestDistance < 0.5
          });
        }

        if (bestMatch && bestDistance < 0.5) {
          onPersonRecognized(bestMatch);
          break;
        }
      }
    } catch (err) {
      console.error("Detection error:", err);
    }
  }, [isLoaded, employeesWithDescriptors, onPersonRecognized, debug]);

  useEffect(() => {
    loadFaceApiModels().then(() => startCamera());
  }, [loadFaceApiModels, startCamera, cameraIndex]);

  useEffect(() => {
    if (!isLoaded) return;
    intervalRef.current = setInterval(detectFaces, 1000);
    return () => clearInterval(intervalRef.current);
  }, [isLoaded, detectFaces]);

  return (
    <>
      {/* Camera video — visible in debug, hidden in production */}
      <video
        ref={videoRef}
        muted
        playsInline
        className={debug
          ? "absolute bottom-4 left-4 w-64 h-48 object-cover rounded-xl border-2 border-white/20 z-20"
          : "absolute opacity-0 pointer-events-none"}
        style={debug ? { transform: "scaleX(-1)" } : { width: 1, height: 1 }}
      />

      {/* Face detection box overlay (debug only) */}
      {debug && (
        <canvas
          ref={overlayCanvasRef}
          className="absolute bottom-4 left-4 w-64 h-48 z-21 pointer-events-none rounded-xl"
          style={{ zIndex: 21 }}
        />
      )}

      {/* Debug info panel */}
      {debug && (
        <div className="absolute bottom-4 left-72 z-20 bg-black/70 text-white text-xs font-mono rounded-xl p-3 w-64 space-y-2 backdrop-blur-sm border border-white/10">
          <div className="font-bold text-yellow-400 text-sm">🔍 Debug Panel</div>

          <div className="flex justify-between">
            <span className="text-white/60">Models:</span>
            <span className={isLoaded ? "text-green-400" : "text-yellow-400"}>{isLoaded ? "✓ Loaded" : "Loading..."}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/60">Camera:</span>
            <span className={cameraError ? "text-red-400" : "text-green-400"}>{cameraError ? "✗ Error" : "✓ Active"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/60">DB faces:</span>
            <span className="text-white">{employeesWithDescriptors.length} / {employees.length}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-white/60">Faces seen:</span>
            <span className="text-white">{debugInfo?.facesDetected ?? 0}</span>
          </div>

          {debugInfo?.bestMatch ? (
            <div className="border-t border-white/10 pt-2 space-y-2">
              <div className="text-white/60">Best match:</div>
              <div className="flex items-center gap-2">
                {debugInfo.bestMatch.photo_url && (
                  <img src={debugInfo.bestMatch.photo_url} className="w-10 h-10 rounded-lg object-cover border border-white/20" />
                )}
                <div>
                  <div className="text-white font-semibold">{debugInfo.bestMatch.name}</div>
                  <div className={`text-xs ${debugInfo.matched ? "text-green-400" : "text-red-400"}`}>
                    dist: {debugInfo.bestMatch.distance.toFixed(3)} {debugInfo.matched ? "✓ MATCH" : `✗ >${debugInfo.threshold}`}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-white/40 text-xs border-t border-white/10 pt-2">No face in frame</div>
          )}
        </div>
      )}

      {/* Status dot (always visible) */}
      <div className="absolute top-6 left-6 z-10 flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${cameraError ? "bg-red-500" : isLoaded ? "bg-green-500 animate-pulse" : "bg-yellow-500 animate-pulse"}`} />
        <span className="text-white/30 text-xs font-body">{status}</span>
      </div>
    </>
  );
}