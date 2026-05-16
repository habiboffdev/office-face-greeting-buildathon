import { useState, useRef, useCallback, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import { loadFaceApi } from "@/lib/faceApiLoader";
import { ArrowLeft, Camera, Upload, RefreshCw, CheckCircle2, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";

export default function EmployeeForm({ employee, companyId, onSave, onCancel }) {
  const [form, setForm] = useState({
    name: employee?.name || "",
    position: employee?.position || "",
    department: employee?.department || "",
    greeting_message: employee?.greeting_message || "",
    birth_date: employee?.birth_date || "",
    photo_url: employee?.photo_url || "",
    face_descriptor: employee?.face_descriptor || [],
    is_active: employee?.is_active !== false
  });

  const [saving, setSaving] = useState(false);
  const [captureMode, setCaptureMode] = useState(false);
  const [isCameraOn, setIsCameraOn] = useState(false);
  const [faceStatus, setFaceStatus] = useState(
    employee?.face_descriptor?.length > 0 ? "ready" : "none"
  );
  const [faceApiLoaded, setFaceApiLoaded] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [processingFace, setProcessingFace] = useState(false);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const faceApiRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadFaceApiModels();
    return () => stopCamera();
  }, []);

  const loadFaceApiModels = async () => {
    try {
      const faceapi = await loadFaceApi();
      faceApiRef.current = faceapi;
      setFaceApiLoaded(true);
    } catch (err) {
      console.error("Failed to load face-api", err);
    }
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setIsCameraOn(true);
      }
    } catch (err) {
      alert("Cannot access camera. Please check permissions.");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      setIsCameraOn(false);
    }
  };

  const capturePhoto = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    const canvas = canvasRef.current;
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    canvas.getContext("2d").drawImage(videoRef.current, 0, 0);

    setProcessingFace(true);
    setFaceStatus("processing");

    // Extract face descriptor
    const faceapi = faceApiRef.current;
    if (faceapi && faceApiLoaded) {
      try {
        const detection = await faceapi
          .detectSingleFace(canvas, new faceapi.TinyFaceDetectorOptions({ scoreThreshold: 0.5 }))
          .withFaceLandmarks(true)
          .withFaceDescriptor();

        if (detection) {
          const descriptor = Array.from(detection.descriptor);
          setForm((prev) => ({ ...prev, face_descriptor: descriptor }));
          setFaceStatus("ready");
        } else {
          setFaceStatus("no_face");
        }
      } catch (err) {
        setFaceStatus("error");
      }
    }

    // Upload photo
    canvas.toBlob(async (blob) => {
      const file = new File([blob], "face.jpg", { type: "image/jpeg" });
      const { file_url } = await base44.integrations.Core.UploadFile({ file });
      setForm((prev) => ({ ...prev, photo_url: file_url }));
      setProcessingFace(false);
    }, "image/jpeg", 0.9);

    stopCamera();
    setCaptureMode(false);
  };

  const handlePhotoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadingPhoto(true);
    setFaceStatus("processing");
    setProcessingFace(true);

    // Upload first
    const { file_url } = await base44.integrations.Core.UploadFile({ file });
    setForm((prev) => ({ ...prev, photo_url: file_url }));

    // Extract face descriptor using a fresh offscreen canvas (not the hidden ref)
    const faceapi = faceApiRef.current;
    if (!faceapi || !faceApiLoaded) {
      setFaceStatus("error");
      setProcessingFace(false);
      setUploadingPhoto(false);
      return;
    }

    try {
      // Draw image onto an offscreen canvas (not hidden via CSS)
      const offscreen = document.createElement("canvas");
      const img = await new Promise((resolve, reject) => {
        const i = new Image();
        i.crossOrigin = "anonymous";
        i.onload = () => resolve(i);
        i.onerror = reject;
        // Add cache-busting to avoid CORS issues
        i.src = file_url + (file_url.includes("?") ? "&" : "?") + "t=" + Date.now();
      });

      offscreen.width = img.naturalWidth || img.width;
      offscreen.height = img.naturalHeight || img.height;
      offscreen.getContext("2d").drawImage(img, 0, 0);

      const detection = await faceapi
        .detectSingleFace(offscreen, new faceapi.TinyFaceDetectorOptions({ scoreThreshold: 0.3, inputSize: 416 }))
        .withFaceLandmarks(true)
        .withFaceDescriptor();

      if (detection) {
        setForm((prev) => ({ ...prev, face_descriptor: Array.from(detection.descriptor) }));
        setFaceStatus("ready");
      } else {
        setFaceStatus("no_face");
      }
    } catch (err) {
      console.error("Face detection error:", err);
      setFaceStatus("error");
    }

    setProcessingFace(false);
    setUploadingPhoto(false);
  };

  const handleSave = async () => {
    if (!form.name.trim()) return alert("Name is required");
    setSaving(true);
    if (employee) {
      await base44.entities.Employee.update(employee.id, form);
    } else {
      await base44.entities.Employee.create({ ...form, company_id: companyId });
    }
    setSaving(false);
    onSave();
  };

  const faceStatusInfo = {
    none: { icon: AlertCircle, color: "text-muted-foreground", text: "No face data" },
    processing: { icon: Loader2, color: "text-yellow-500", text: "Processing face..." },
    ready: { icon: CheckCircle2, color: "text-green-500", text: "Face data captured" },
    no_face: { icon: AlertCircle, color: "text-orange-500", text: "No face detected — try again" },
    error: { icon: AlertCircle, color: "text-destructive", text: "Error processing face" },
  };
  const fsi = faceStatusInfo[faceStatus];

  return (
    <div className="max-w-2xl">
      <button onClick={onCancel} className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Back to employees
      </button>

      <h2 className="text-xl font-semibold font-display mb-6">
        {employee ? "Edit Employee" : "Add Employee"}
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left: Form */}
        <div className="space-y-4">
          <div>
            <Label>Full Name *</Label>
            <Input
              className="mt-1"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              placeholder="John Smith"
            />
          </div>
          <div>
            <Label>Position</Label>
            <Input
              className="mt-1"
              value={form.position}
              onChange={(e) => setForm((p) => ({ ...p, position: e.target.value }))}
              placeholder="Software Engineer"
            />
          </div>
          <div>
            <Label>Department</Label>
            <Input
              className="mt-1"
              value={form.department}
              onChange={(e) => setForm((p) => ({ ...p, department: e.target.value }))}
              placeholder="Engineering"
            />
          </div>
          <div>
            <Label>Birth Date</Label>
            <Input
              className="mt-1"
              type="date"
              value={form.birth_date}
              onChange={(e) => setForm((p) => ({ ...p, birth_date: e.target.value }))}
            />

          </div>
          <div>
            <Label>Custom Greeting</Label>
            <Textarea
              className="mt-1"
              value={form.greeting_message}
              onChange={(e) => setForm((p) => ({ ...p, greeting_message: e.target.value }))}
              placeholder={`Welcome, ${form.name || "[Name]"}!`}
              rows={2}
            />

          </div>
          <div className="flex items-center gap-3">
            <Switch
              checked={form.is_active}
              onCheckedChange={(v) => setForm((p) => ({ ...p, is_active: v }))}
            />
            <Label>Active in recognition system</Label>
          </div>
        </div>

        {/* Right: Photo & Face */}
        <div className="space-y-4">
          <div>
            <Label>Face Photo</Label>
            <div className="mt-2 space-y-3">
              {/* Preview */}
              <div className="w-full aspect-square max-w-48 rounded-xl overflow-hidden bg-muted border border-border mx-auto relative">
                {captureMode && isCameraOn ? (
                  <video ref={videoRef} className="w-full h-full object-cover" muted playsInline />
                ) : form.photo_url ? (
                  <img src={form.photo_url} alt="Preview" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                    <Camera className="w-10 h-10 opacity-30" />
                  </div>
                )}
                {(uploadingPhoto || processingFace) && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <Loader2 className="w-8 h-8 text-white animate-spin" />
                  </div>
                )}
              </div>
              <canvas ref={canvasRef} style={{ position: "absolute", top: -9999, left: -9999, width: 1, height: 1 }} />

              {/* Face status */}
              <div className={`flex items-center gap-2 text-sm ${fsi.color}`}>
                <fsi.icon className={`w-4 h-4 ${faceStatus === "processing" ? "animate-spin" : ""}`} />
                {fsi.text}
              </div>

              {/* Buttons */}
              {captureMode && isCameraOn ? (
                <div className="flex gap-2">
                  <Button className="flex-1" onClick={capturePhoto} disabled={processingFace}>
                    <Camera className="w-4 h-4 mr-2" />
                    Capture
                  </Button>
                  <Button variant="outline" onClick={() => { stopCamera(); setCaptureMode(false); }}>
                    Cancel
                  </Button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    disabled={!faceApiLoaded}
                    onClick={() => { setCaptureMode(true); startCamera(); }}
                  >
                    <Camera className="w-4 h-4 mr-1" />
                    Camera
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadingPhoto}
                  >
                    <Upload className="w-4 h-4 mr-1" />
                    Upload
                  </Button>
                </div>
              )}

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handlePhotoUpload}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="flex gap-3 mt-8 pt-6 border-t border-border">
        <Button onClick={handleSave} disabled={saving || !form.name} className="px-8">
          {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
          {employee ? "Save Changes" : "Add Employee"}
        </Button>
        <Button variant="outline" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}