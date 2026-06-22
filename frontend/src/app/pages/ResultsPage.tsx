import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Download,
  FileText,
  Video,
  CheckCircle,
  Eye,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import VideoPlayer from "../components/VideoPlayer";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "../components/ui/dialog";

import { toast } from "sonner";
// Updated Document type to include all used properties
export interface Document {
  id: string;
  name: string;
  basename?: string;
  latest_basename?: string;
  fileType: string;
  slides?: any[];
  slides_count?: number;
  generated_at?: string;
  generationMode?: 'pptx' | 'video';
  output_type?: string;
  outputs?: {
    mp4Url?: string;
    // ...other output fields
  };
  body?: string;
  // ...other fields as needed
}

const API_BASE =
  (import.meta as any).env?.VITE_API_URL || "http://localhost:8000";

interface ResultsPageProps {
  getDocument: (id: string | undefined) => Document | null;
}

export default function ResultsPage({ getDocument }: ResultsPageProps) {
  const { id } = useParams();
  const navigate = useNavigate();

  const [document, setDocument] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  /* ---------- Preview State ---------- */
  const [pptxPreviewOpen, setPptxPreviewOpen] = useState(false);
  const [slideImages, setSlideImages] = useState<string[]>([]);
  const [currentSlide, setCurrentSlide] = useState(0);

  const [videoPlayerOpen, setVideoPlayerOpen] = useState(false);
  const [videoExists, setVideoExists] = useState<boolean | null>(null);
  
  const hasVideo = (() => {
    if (!document) return false;
    const outputType = (document as any).output_type?.toLowerCase() || '';
    // Show video container if output_type includes 'video'
    // Video existence check is only for playing/downloading
    return outputType.includes('video') || outputType.includes('pptx+video');
  })();

  const isUuid = (value: string | undefined) => !!value && /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(value);

  /* ---------- Load document ---------- */
  useEffect(() => {
    if (!id || id === 'undefined') {
      setLoadError('No document ID provided');
      setLoading(false);
      return;
    }

    const loadDocByBasename = () => {
      setDocument({
        id,
        name: id.replace(/_v\d+$/, '').replace(/_/g, ' '),
        basename: id,
        fileType: 'pptx',
        generationMode: 'video',
        output_type: 'pptx+video',
        outputs: {},
      });
      setLoading(false);
    };

    if (!isUuid(id)) {
      loadDocByBasename();
      return;
    }

    const abortController = new AbortController();
    const timeoutId = setTimeout(() => {
      abortController.abort();
      console.warn(`Document fetch timeout for ${id}, using as basename`);
      loadDocByBasename();
    }, 5000); // 5 second timeout

    fetch(`${API_BASE}/api/documents/${id}`, { signal: abortController.signal })
      .then((r) => {
        if (!r.ok) {
          throw new Error('Document not found by id, treating as basename');
        }
        return r.json();
      })
      .then(setDocument)
      .catch((err) => {
        console.warn(`Could not fetch document by id ${id}, using as basename:`, err);
        loadDocByBasename();
      })
      .finally(() => {
        clearTimeout(timeoutId);
        setLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      abortController.abort();
    };
  }, [id]);

  /* ---------- Always fetch PPTX preview slide count ---------- */
  const [previewSlidesCount, setPreviewSlidesCount] = useState<number | null>(null);
  const currentBasename =
    document?.latest_basename || document?.basename || (document?.name ? document.name.replace(/\.[^/.]+$/, "") : undefined);

  useEffect(() => {
    if (!document) return;
    if (!currentBasename) return;

    fetch(`${API_BASE}/api/preview/slides/${currentBasename}`)
      .then((r) => r.json())
      .then((data) => {
        setPreviewSlidesCount(typeof data.slides_count === 'number' ? data.slides_count : (data.slides?.length || 0));
      });
  }, [document, currentBasename]);

  /* ---------- Check if video exists ---------- */
  useEffect(() => {
    if (!currentBasename) return;

    fetch(`${API_BASE}/api/results/video/${currentBasename}`)
      .then((r) => setVideoExists(r.ok))
      .catch(() => setVideoExists(false));
  }, [currentBasename]);


   // Always use previewSlidesCount if available, otherwise fallback to DB or slides array
  const slidesCount =
    previewSlidesCount !== null
      ? previewSlidesCount
      : (typeof document?.slides_count === 'number'
        ? document.slides_count
        : (document?.slides?.length || 0));

        
  /* ---------- Load PPTX preview images ---------- */
  useEffect(() => {
    if (!pptxPreviewOpen || !currentBasename) return;

    const loadPreviewSlides = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/preview/slides/${currentBasename}`);
        if (!res.ok) {
          throw new Error(`Preview slides not available: ${res.statusText}`);
        }

        const data = await res.json();
        const urls = Array.isArray(data.slides)
          ? data.slides.map((path: string) =>
              path.startsWith("http") ? path : `${API_BASE}${path}`
            )
          : [];

        setSlideImages(urls);
        setPreviewSlidesCount(
          typeof data.slides_count === "number"
            ? data.slides_count
            : urls.length
        );
        setCurrentSlide(0);
      } catch (err) {
        console.error("Failed to load preview slides", err);
        setSlideImages([]);
      }
    };

    loadPreviewSlides();
  }, [pptxPreviewOpen, currentBasename]);

  const handleDownload = (type: "pptx" | "mp4") => {
    if (!document || !currentBasename) return;

    const url =
      type === "pptx"
        ? `${API_BASE}/api/results/pptx/${currentBasename}`
        : `${API_BASE}/api/results/video/${currentBasename}`;

    const a = window.document.createElement("a");
    a.href = url;
    a.download = `${currentBasename}.${type}`;
    if (window.document.body) {
      window.document.body.appendChild(a);
      a.click();
      window.document.body.removeChild(a);
    } else {
      a.click();
    }

    toast.success(`Downloading ${type.toUpperCase()}`);
  };


 

  const getVideoUrl = () => {
    const mp4Url = document?.outputs?.mp4Url || (document?.basename ? `/api/results/video/${encodeURIComponent(document.basename)}` : undefined);
    if (!mp4Url) return null;
    
    const baseUrl = mp4Url.startsWith("http")
      ? mp4Url
      : `${API_BASE}${mp4Url}`;
    
    const timestamp = `t=${Date.now()}`;
    return baseUrl.includes("?") 
      ? `${baseUrl}&${timestamp}`
      : `${baseUrl}?${timestamp}`;
  };

  /* ---------- UI ---------- */
  if (loading) {
    return (
      <div className="p-8 text-center">
        <div className="inline-block">
          <div className="animate-spin mb-4">
            <CheckCircle className="w-8 h-8 text-indigo-600 mx-auto" />
          </div>
          <p className="text-slate-600 font-medium">Finalizing your presentation…</p>
          <p className="text-xs text-slate-500 mt-2">This may take a moment</p>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-8 text-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md mx-auto">
          <p className="text-red-700 font-semibold mb-4">Unable to load results</p>
          <p className="text-red-600 text-sm mb-4">{loadError}</p>
          <Button onClick={() => navigate("/library")}>Back to Library</Button>
        </div>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="p-8 text-center">
        <Button onClick={() => navigate("/library")}>Back to Library</Button>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="max-w-4xl mx-auto space-y-8">

        {/* ✅ Success Banner */}
        <div className="bg-gradient-to-r from-emerald-500 to-teal-500 page-hero-container text-white shadow-xl">
          <div className="flex gap-3 items-center">
            <div className="w-10 h-10 bg-white/20 rounded-2xl flex items-center justify-center">
              <CheckCircle className="w-5 h-5" />
            </div>
            <div>
              <h1 className="page-hero-title">Processing Complete!</h1>
              <p className="page-hero-subtitle text-emerald-100">
                {hasVideo ? 'Your presentation and video are ready.' : 'Your presentation is ready.'}
              </p>
            </div>
          </div>
        </div>

        {/* ✅ Document Info */}
        <Card className="border-indigo-100 shadow-lg bg-white/80 backdrop-blur-sm">
          <CardHeader className="bg-gradient-to-r from-indigo-50 to-purple-50">
            <CardTitle>Document Information</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-slate-500">Document Name</p>
                <p>{document.name}</p>
              </div>
              <div>
                <p className="text-slate-500">File Type</p>
                <p>{document.fileType}</p>
              </div>
              <div>
                <p className="text-slate-500">Slides Generated</p>
                <p>{slidesCount} slides</p>
              </div>
              <div>
                <p className="text-slate-500">Generated At</p>
                <p>{document.generated_at ? new Date(document.generated_at).toLocaleString() : "Just now"}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ✅ Output Cards */}
        <div className={`grid grid-cols-1 ${hasVideo ? 'md:grid-cols-2' : ''} gap-6`}>

          {/* PPTX Card */}
          <Card className="border-indigo-100 shadow-lg bg-gradient-to-br from-white to-indigo-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center">
                  <FileText className="w-4 h-4 text-white" />
                </div>
                PowerPoint Presentation
              </CardTitle>
              <CardDescription>
                Editable PPTX • {slidesCount} slides
              </CardDescription>
            </CardHeader>

            <CardContent className="mt-4 space-y-4">
              <div className="bg-gradient-to-br from-indigo-100 to-purple-100 rounded-xl p-8 flex justify-center border-2 border-indigo-200">
                <FileText className="w-16 h-16 text-indigo-600" />
              </div>

              {/* ✅ Processing Summary */}
              <div className="text-sm text-slate-700 space-y-1">
                <p>• {slidesCount} slides</p>
                <p>• Fully editable in PowerPoint</p>
                <p>• Professional design template</p>
              </div>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setPptxPreviewOpen(true)}
                >
                  <Eye className="w-4 h-4 mr-2" /> Preview
                </Button>
                <Button
                  className="flex-1 bg-gradient-to-r from-indigo-600 to-purple-600"
                  onClick={() => handleDownload("pptx")}
                >
                  <Download className="w-4 h-4 mr-2" /> Download
                </Button>
              </div>
            </CardContent>
          </Card>

          {hasVideo && (
            <Card className="border-purple-100 shadow-lg bg-gradient-to-br from-white to-purple-50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                    <Video className="w-4 h-4 text-white" />
                  </div>
                  Narrated Video
                </CardTitle>
                <CardDescription className="mb-3">
                  MP4 • video with AI-generated narration
                </CardDescription>
              </CardHeader>

              <CardContent className="mt-4 space-y-4">
                <div className="bg-gradient-to-br from-purple-100 to-pink-100 rounded-xl p-8 flex justify-center border-2 border-purple-200">
                  <Video className="w-16 h-16 text-purple-600" />
                </div>

                {/* ✅ Processing Summary */}
                <div className="text-sm text-slate-700 space-y-1">
                  <p>• 1920×1080 HD quality</p>
                  <p>• AI-generated voice narration</p>
                  <p>• Ready to share and present</p>
                </div>

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => {
                      const url = getVideoUrl();
                      if (!url) {
                        toast.error("Video is not available yet.");
                        return;
                      }
                      setVideoPlayerOpen(true);
                    }}
                  >
                    <Eye className="w-4 h-4 mr-2" /> Preview
                  </Button>
                  <Button
                    className="flex-1 bg-gradient-to-r from-purple-600 to-pink-600"
                    onClick={() => handleDownload("mp4")}
                    disabled={videoExists === false}
                  >
                    <Download className="w-4 h-4 mr-2" /> Download
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* ✅ Navigation Actions */}
        <div className="flex flex-col sm:flex-row gap-4 pt-4">
          <Button
            variant="outline"
            className="flex-1 border-indigo-200 text-indigo-700 hover:bg-indigo-50"
            onClick={() => navigate("/library")}
          >
            <ChevronLeft className="w-4 h-4 mr-2" />
            Back to Library
          </Button>

          <Button
            variant="outline"
            className="flex-1 border-purple-200 text-purple-700 hover:bg-purple-50"
            onClick={() => navigate("/upload")}
          >
            Upload New Document
          </Button>
        </div>



{/* ✅ LARGE PPTX PREVIEW */}
<Dialog open={pptxPreviewOpen} onOpenChange={setPptxPreviewOpen}>
  <DialogContent
    className="bg-gradient-to-br from-slate-50 to-slate-100 fixed top-[50%] left-[50%] z-50 w-[99vw] max-w-[1920px] h-[85vh] translate-x-[-50%] translate-y-[-50%] flex flex-col p-0 overflow-hidden rounded-2xl shadow-2xl"
  >
    {/* ✅ Header */}
    <DialogHeader className="px-6 py-3 border-b bg-white/70 backdrop-blur flex-shrink-0">
      <DialogTitle className="text-lg font-semibold">
        Slide Preview
      </DialogTitle>

      <DialogDescription className="flex items-center justify-between text-sm">
        <span className="truncate">{document.name}</span>

        {/* ✅ Slide Counter Badge */}
        <span className="px-3 py-1 rounded-full bg-indigo-100 text-indigo-700 font-medium text-xs">
          {currentSlide + 1} / {slidesCount}
        </span>
      </DialogDescription>
    </DialogHeader>

    {/* ✅ Slide Viewer */}
    <div className="flex flex-1 items-center justify-center relative px-4 py-4 min-h-0">

      {/* ✅ Left Arrow */}
      <Button
        variant="ghost"
        disabled={currentSlide === 0}
        onClick={() => setCurrentSlide((s) => s - 1)}
        className="absolute left-4 top-1/2 -translate-y-1/2 rounded-full shadow-lg bg-white/90 backdrop-blur hover:bg-white z-10"
      >
        <ChevronLeft size={32} />
      </Button>

      {/* ✅ Slide Image FULLY OCCUPY */}
      <div className="flex items-center justify-center w-full h-full min-h-0">
        {slideImages.length > 0 && (
          <img
            src={slideImages[currentSlide]}
            
            onError={(e) => {
                e.currentTarget.style.display = "none";
              }}

            className="w-full h-full object-contain rounded-xl shadow-xl bg-white"
          />
        )}
      </div>

      {/* ✅ Right Arrow */}
      <Button
        variant="ghost"
        disabled={currentSlide === slideImages.length - 1}
        onClick={() => setCurrentSlide((s) => s + 1)}
        className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full shadow-lg bg-white/90 backdrop-blur hover:bg-white z-10"
      >
        <ChevronRight size={32} />
      </Button>
    </div>

    {/* ✅ Footer */}
    <div className="px-6 py-2 border-t text-xs text-slate-500 flex justify-center bg-white/60 backdrop-blur flex-shrink-0">
      Use arrows to navigate slides
    </div>
  </DialogContent>
</Dialog>

        {/* ✅ LARGE VIDEO PREVIEW */}
        {videoPlayerOpen && (
          <VideoPlayer
            videoUrl={getVideoUrl() ?? undefined}
            slides={document.slides as any}
            onClose={() => setVideoPlayerOpen(false)}
            docId={currentBasename || document.id}
          />
        )}

      </div>
    </div>
  );
}

