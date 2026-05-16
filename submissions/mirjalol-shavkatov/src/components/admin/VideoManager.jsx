import { useState, useEffect } from "react";
import { useCompany } from "@/lib/CompanyContext";
import { base44 } from "@/api/base44Client";
import { Plus, Trash2, Play, Loader2, Video as VideoIcon, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

export default function VideoManager() {
  const { activeCompany } = useCompany();
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [newVideo, setNewVideo] = useState({ title: "", video_url: "", order: 0 });
  const [uploadFile, setUploadFile] = useState(null);
  const [previewVideo, setPreviewVideo] = useState(null);
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkProgress, setBulkProgress] = useState({ done: 0, total: 0 });

  useEffect(() => {
    if (activeCompany) loadVideos();
  }, [activeCompany]);

  const loadVideos = async () => {
    setLoading(true);
    const data = await base44.entities.Video.filter({ company_id: activeCompany.id }, "order", 100);
    setVideos(data.sort((a, b) => (a.order || 0) - (b.order || 0)));
    setLoading(false);
  };

  const handleDelete = async (id) => {
    if (!confirm("Remove this video from the playlist?")) return;
    await base44.entities.Video.delete(id);
    setVideos((prev) => prev.filter((v) => v.id !== id));
  };

  const handleToggle = async (video) => {
    await base44.entities.Video.update(video.id, { is_active: !video.is_active });
    setVideos((prev) => prev.map((v) => (v.id === video.id ? { ...v, is_active: !v.is_active } : v)));
  };

  const handleBulkUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    setBulkUploading(true);
    setBulkProgress({ done: 0, total: files.length });

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const { file_url } = await base44.integrations.Core.UploadFile({ file });
      const title = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
      await base44.entities.Video.create({
        title,
        video_url: file_url,
        order: videos.length + i,
        is_active: true,
        company_id: activeCompany.id,
      });
      setBulkProgress({ done: i + 1, total: files.length });
    }

    setBulkUploading(false);
    setBulkProgress({ done: 0, total: 0 });
    e.target.value = "";
    loadVideos();
  };

  const handleAdd = async () => {
    if (!newVideo.title.trim()) return alert("Title is required");
    let videoUrl = newVideo.video_url;

    setUploading(true);
    if (uploadFile) {
      const { file_url } = await base44.integrations.Core.UploadFile({ file: uploadFile });
      videoUrl = file_url;
    }

    if (!videoUrl) { setUploading(false); return alert("Please provide a video URL or upload a file"); }

    await base44.entities.Video.create({
      title: newVideo.title,
      video_url: videoUrl,
      order: videos.length,
      is_active: true,
      company_id: activeCompany.id,
    });

    setUploading(false);
    setShowAdd(false);
    setNewVideo({ title: "", video_url: "", order: 0 });
    setUploadFile(null);
    loadVideos();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold font-display">Video Playlist</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {videos.filter((v) => v.is_active).length} active videos
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className={`cursor-pointer inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground transition-colors ${bulkUploading ? "opacity-50 pointer-events-none" : ""}`}>
            {bulkUploading
              ? <><Loader2 className="w-4 h-4 animate-spin" /> {bulkProgress.done}/{bulkProgress.total}</>
              : <><UploadCloud className="w-4 h-4" /> Bulk Upload</>
            }
            <input type="file" accept="video/*" multiple className="hidden" onChange={handleBulkUpload} disabled={bulkUploading} />
          </label>
          <Button onClick={() => setShowAdd(true)} className="gap-2">
            <Plus className="w-4 h-4" />
            Add Video
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array(4).fill(0).map((_, i) => (
            <div key={i} className="h-20 rounded-xl bg-muted animate-pulse" />
          ))}
        </div>
      ) : videos.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <VideoIcon className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="font-medium">No videos yet</p>
          <p className="text-sm mt-1">Add videos to start the display playlist</p>
        </div>
      ) : (
        <div className="space-y-3">
          {videos.map((video, index) => (
            <div
              key={video.id}
              className={`bg-card border rounded-xl p-4 flex items-center gap-4 ${
                video.is_active ? "border-border" : "border-border opacity-50"
              }`}
            >
              <div className="flex-shrink-0 text-muted-foreground text-sm w-6 text-center font-mono">
                {index + 1}
              </div>

              {/* Thumbnail placeholder */}
              <div className="w-16 h-10 bg-muted rounded-lg flex-shrink-0 flex items-center justify-center overflow-hidden">
                <VideoIcon className="w-5 h-5 text-muted-foreground opacity-50" />
              </div>

              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{video.title}</p>
                <p className="text-xs text-muted-foreground truncate mt-0.5">{video.video_url}</p>
              </div>

              <div className="flex items-center gap-3">
                <Badge
                  variant="secondary"
                  className={`text-xs ${video.is_active ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground"}`}
                >
                  {video.is_active ? "Active" : "Inactive"}
                </Badge>
                <Switch checked={video.is_active} onCheckedChange={() => handleToggle(video)} />
                <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => setPreviewVideo(video)}>
                  <Play className="w-3.5 h-3.5" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => handleDelete(video.id)}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Video Dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Video</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Title *</Label>
              <Input
                className="mt-1"
                value={newVideo.title}
                onChange={(e) => setNewVideo((p) => ({ ...p, title: e.target.value }))}
                placeholder="Promo Video 1"
              />
            </div>
            <div>
              <Label>Video URL</Label>
              <Input
                className="mt-1"
                value={newVideo.video_url}
                onChange={(e) => setNewVideo((p) => ({ ...p, video_url: e.target.value }))}
                placeholder="https://..."
              />
            </div>
            <div className="text-center text-sm text-muted-foreground">— or —</div>
            <div>
              <Label>Upload Video File</Label>
              <Input
                className="mt-1"
                type="file"
                accept="video/*"
                onChange={(e) => {
                  const file = e.target.files[0];
                  if (!file) return;
                  setUploadFile(file);
                  // Auto-fill title from filename if title is empty
                  if (!newVideo.title.trim()) {
                    const nameWithoutExt = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
                    setNewVideo((p) => ({ ...p, title: nameWithoutExt }));
                  }
                }}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button>
            <Button onClick={handleAdd} disabled={uploading}>
              {uploading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Add Video
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview Dialog */}
      <Dialog open={!!previewVideo} onOpenChange={() => setPreviewVideo(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{previewVideo?.title}</DialogTitle>
          </DialogHeader>
          <video src={previewVideo?.video_url} controls className="w-full rounded-lg" autoPlay />
        </DialogContent>
      </Dialog>
    </div>
  );
}