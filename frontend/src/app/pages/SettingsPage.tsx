import { useEffect, useState } from 'react';
import { Video, MessageSquare, Play, FileText, Clock } from 'lucide-react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import VideoPlayer from '../components/VideoPlayer';

const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

interface Slide {
  id: string;
  title: string;
  content: string;
  audioScript: string;
  timestamp: number;
}

interface VideoDocument {
  id: string;
  name: string;
  fileType?: string;
  status?: string;
  size?: string;
  createdDate?: string;
  generated_at?: string;
  slides_count?: number;
  basename?: string;
  latest_basename?: string;
  outputs?: {
    mp4Url?: string;
    pptxUrl?: string;
  };
  thumbnail?: string;
  duration?: string | number;
  slides?: Slide[];
  videoUrl?: string;
}

const getPosterUrl = (video: VideoDocument) => {
  const rawName = video.latest_basename || video.basename || video.name?.replace(/\.[^/.]+$/, '');
  if (!rawName) return undefined;

  const normalized = rawName.replace(/\\/g, '/');
  const parts = normalized.split('/').filter(Boolean);

  const encodePath = (value: string) =>
    value
      .split('/')
      .filter(Boolean)
      .map(encodeURIComponent)
      .join('/');

  const buildUrl = (base: string, version: string) =>
    `${API_BASE}/projects/${encodePath(base)}/${encodeURIComponent(version)}/slides_images/Slide1.JPG`;

  if (parts.length >= 2) {
    const version = parts[parts.length - 1];
    const base = parts.slice(0, -1).join('/');
    return buildUrl(base, version);
  }

  const match = normalized.match(/^(.*?)[_-]?v(\d+)$/i);
  if (match) {
    return buildUrl(match[1], `v${match[2]}`);
  }

  return buildUrl(normalized, 'v1');
};

export default function SettingsPage() {
  const [selectedVideo, setSelectedVideo] = useState<VideoDocument | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [documents, setDocuments] = useState<VideoDocument[]>([]);
  useEffect(() => {
    const cached = sessionStorage.getItem('video_docs');
    if (cached) {
      try {
        setDocuments(JSON.parse(cached));
      } catch {
        console.warn("Invalid video cache, clearing...");
        sessionStorage.removeItem('video_docs');
      }
    }
  }, []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [slideCounts, setSlideCounts] = useState<Record<string, number>>({});
  const [slideDurations, setSlideDurations] = useState<Record<string, number>>({});
  const [showAllVideos, setShowAllVideos] = useState(false);
  // Helper to format seconds as mm:ss
  const formatTime = (time: number) => {
    if (!isFinite(time) || time < 0) return '00:00';
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };



  const getDocumentBaseName = (doc: VideoDocument) => {
    return (
      doc.basename ||
      doc.latest_basename ||
      doc.name?.replace(/\.[^/.]+$/, '') ||
      undefined
    );
  };

  const parseDurationValue = (value: string | number | undefined): number | undefined => {
    if (typeof value === 'number') {
      return value >= 0 && isFinite(value) ? value : undefined;
    }

    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (/^\d+(?:\.\d+)?$/.test(trimmed)) {
        const parsed = Number(trimmed);
        return parsed >= 0 && isFinite(parsed) ? parsed : undefined;
      }

      const parts = trimmed.split(':').map((part) => Number(part));
      if (parts.length === 2 && parts.every((n) => !Number.isNaN(n))) {
        const [minutes, seconds] = parts;
        if (seconds >= 0 && seconds < 60 && minutes >= 0) {
          return minutes * 60 + seconds;
        }
      }

      if (parts.length === 3 && parts.every((n) => !Number.isNaN(n))) {
        const [hours, minutes, seconds] = parts;
        if (
          hours >= 0 &&
          minutes >= 0 && minutes < 60 &&
          seconds >= 0 && seconds < 60
        ) {
          return hours * 3600 + minutes * 60 + seconds;
        }
      }
    }

    return undefined;
  };

  const normalizeDocumentDuration = (doc: VideoDocument) => {
    return { ...doc, duration: parseDurationValue(doc.duration) };
  };

  const fetchDocuments = async () => {
    const res = await fetch(`${API_BASE}/api/documents?page=1&limit=1000`);
    if (!res.ok) {
      throw new Error(`Failed to load documents: ${res.status}`);
    }
    const data = await res.json();
    return (data.items || []).map(normalizeDocumentDuration);
  };

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    fetchDocuments()
      .then((items) => {
        setDocuments(items);

        // ✅ SAVE
        sessionStorage.setItem('video_docs', JSON.stringify(items));
      })
      .catch((err: any) => {
        if (!isMounted) return;
        setError(err.message || 'Failed to load documents');
      })
      .finally(() => {
        if (!isMounted) return;
        setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch slide counts and durations for each document using the preview/process API
  useEffect(() => {
    if (!documents.length) return;
    let cancelled = false;
    const fetchCountsAndDurations = async () => {
      const counts: Record<string, number> = {};
      const durations: Record<string, number> = {};
      await Promise.all(
        documents.map(async (doc) => {
          const base = getDocumentBaseName(doc);
          if (!base) return;
          try {
            // Get slide count
            const res = await fetch(`${API_BASE}/api/preview/slides/${base}`);
            if (res.ok) {
              const data = await res.json();
              counts[doc.id] = typeof data.slides_count === 'number' ? data.slides_count : (data.slides?.length || 0);
            }
            // Get slide timestamps for duration
            const slidesRes = await fetch(`${API_BASE}/api/process/slides/${encodeURIComponent(base)}`);
            if (slidesRes.ok) {
              const slidePayload = await slidesRes.json();
              const slides = slidePayload?.slides || [];
              if (slides.length > 0) {
                // Get all timestamps
                const timestamps = slides
                  .map((s: any) => s.timestamp)
                  .filter((t: any) => typeof t === 'number' && t >= 0)
                  .sort((a: number, b: number) => a - b);
                
                if (timestamps.length > 0) {
                  // Calculate total duration based on timestamps
                  const lastTimestamp = timestamps[timestamps.length - 1];
                  
                  // Estimate the duration of the last slide
                  let lastSlideDuration = 10; // Default 10 seconds
                  if (timestamps.length > 1) {
                    // Duration of last slide = difference between last and second-to-last timestamp
                    lastSlideDuration = Math.max(5, timestamps[timestamps.length - 1] - timestamps[timestamps.length - 2]);
                  }
                  
                  // Total duration = last timestamp + estimated duration of last slide
                  durations[doc.id] = Math.ceil(lastTimestamp + lastSlideDuration);
                  console.log("Durations map:", durations);

                }
              }
            }
          } catch (error) {
            // Log error but don't break
            console.error(`Failed to fetch duration for ${base}:`, error);
          }
        })
      );
      if (!cancelled) {
        setSlideCounts(counts);
        setSlideDurations(durations);
      }
    };
    fetchCountsAndDurations();
    return () => { cancelled = true; };
  }, [documents, API_BASE]);

  const loadDocumentById = async (id: string) => {
    const res = await fetch(`${API_BASE}/api/documents/${id}`);
    if (!res.ok) {
      throw new Error(`Document details request failed: ${res.status}`);
    }
    return res.json() as Promise<VideoDocument>;
  };

  const handleWatchWithChat = async (video: VideoDocument) => {
    setError(null);

    try {
      const doc = await loadDocumentById(video.id);
      const basename = getDocumentBaseName(doc) || doc.name.replace(/\.[^/.]+$/, '');

      let slides: Slide[] = [];
      const slidesRes = await fetch(`${API_BASE}/api/process/slides/${encodeURIComponent(basename)}`);
      if (slidesRes.ok) {
        const slidePayload = await slidesRes.json();
        if (slidePayload?.status === 'completed') {
          slides = slidePayload.slides || [];
        }
      }

      const videoUrl = doc.outputs?.mp4Url
        ? doc.outputs.mp4Url.startsWith('http')
          ? doc.outputs.mp4Url
          : `${API_BASE}${doc.outputs.mp4Url}`
        : undefined;

      const normalizedDuration = parseDurationValue(doc.duration);
      setSelectedVideo({ ...doc, duration: normalizedDuration, slides, videoUrl, basename });
    } catch (err: any) {
      setError(err.message || 'Unable to open video');
    }
  };

  const handleCloseVideo = () => {
    setSelectedVideo(null);
  };


  const filteredVideos = documents.filter((video) => {
    if (!video.name) return false;

    const name = video.name.toLowerCase();

    // ✅ ONLY COMPLETED VIDEOS
    const isCompleted = video.status === 'completed';

    return isCompleted && name.includes(searchQuery.toLowerCase());
  });

  const visibleVideos = showAllVideos ? filteredVideos : filteredVideos.slice(0, 3);

  const getSelectedVideoDuration = (video: VideoDocument | null) => {
    if (!video) return undefined;
    const parsed = parseDurationValue(video.duration);
    if (parsed !== undefined && parsed > 0) {
      return parsed;
    }
    if (video.id && slideDurations[video.id]) {
      return slideDurations[video.id];
    }
    return undefined;
  };

  const selectedVideoDurationSec = getSelectedVideoDuration(selectedVideo);

  const getGradientClass = (type: string) => {
    const gradients: Record<string, string> = {
      'gradient-1': 'from-indigo-500 to-purple-500',
      'gradient-2': 'from-blue-500 to-cyan-500',
      'gradient-3': 'from-purple-500 to-pink-500',
      'gradient-4': 'from-emerald-500 to-teal-500',
      'gradient-5': 'from-orange-500 to-red-500',
      'gradient-6': 'from-violet-500 to-fuchsia-500',
    };
    return gradients[type] || 'from-slate-500 to-slate-700';
  };

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 page-hero-container text-white shadow-xl">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="page-hero-title">Video Library</h1>
              <p className="page-hero-subtitle text-indigo-100">
                Watch and chat with AI about your generated presentations
              </p>
            </div>
            <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-2xl flex items-center justify-center">
              <MessageSquare className="w-6 h-6 text-white" />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex-1">
            <Input
              placeholder="Search videos..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="border-indigo-200 focus:border-indigo-500 focus:ring-indigo-500"
            />
          </div>
          <Badge variant="outline" className="px-4 py-2 text-sm bg-white">
            {filteredVideos.length} Videos
          </Badge>
        </div>

        {selectedVideo ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-900 p-5 text-white shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-indigo-300">Video Presentation</p>
                <h2 className="text-2xl font-semibold">
                  {selectedVideo.name?.replace(/\.[^/.]+$/, '') || 'Untitled'}
                </h2>
              </div>
              <div className="rounded-full bg-white/10 px-3 py-2 text-sm text-white">
                Total Duration: {selectedVideoDurationSec !== undefined ? formatTime(selectedVideoDurationSec) : 'Unknown'}
              </div>
            </div>
          </div>
        ) : null}

        
        {error ? (
          <div className="text-center py-12 text-red-600">{error}</div>
        ) : filteredVideos.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            No completed videos available
          </div>
        ) : (


          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {visibleVideos.length > 0 ? (
                visibleVideos.map((video) => {
                  // Use preview slide count if available, else fallback to DB or slides array
                  const slideCount =
                    slideCounts[video.id] !== undefined
                      ? slideCounts[video.id]
                      : (typeof video.slides_count === 'number'
                          ? video.slides_count
                          : (video.slides?.length || 0));
                  const uploadDate = video.createdDate ? new Date(video.createdDate).toLocaleDateString() : 'Unknown';
                  const videoDate = video.generated_at ? new Date(video.generated_at).toLocaleDateString() : '';
                  const displayDate = videoDate || uploadDate;
                  const title = video.name?.replace(/\.[^/.]+$/, '') || 'Untitled';

                  // Prefer backend duration from document, else fallback to calculated duration
                  let videoDurationSec: number | undefined = parseDurationValue(video.duration);
                  if ((videoDurationSec === undefined || videoDurationSec <= 0) && slideDurations[video.id]) {
                    videoDurationSec = slideDurations[video.id];
                  }

                  const posterUrl = getPosterUrl(video);

                  return (
                    <Card
                      key={video.id}
                      className="border border-slate-200 bg-white hover:border-slate-300 transition-all overflow-hidden group"
                    >
                      <div className="relative h-40 overflow-hidden rounded-t-xl bg-slate-950">
                        <div className={`absolute inset-0 z-0 bg-gradient-to-br ${getGradientClass(video.thumbnail || '')}`} />
                        {posterUrl ? (
                          <img
                            src={posterUrl}
                            alt={`${title} cover`}
                            className="absolute inset-0 w-full h-full object-cover z-10"
                            onError={(e) => {
                              const target = e.currentTarget;
                              if (target.src.endsWith('Slide1.JPG')) {
                                target.src = target.src.replace('Slide1.JPG', 'slides.jpg');
                                return;
                              }
                              target.style.display = 'none';
                            }}
                          />
                        ) : null}
                        <div className="absolute inset-0 z-20 bg-black/25" />
                        <div className="relative z-30 flex items-center justify-center h-full">
                          <Play className="w-14 h-14 text-white opacity-90 group-hover:opacity-100 transition-opacity" />
                        </div>
                        <div className="absolute top-3 right-3 z-30 bg-black/60 backdrop-blur-sm px-2.5 py-1 rounded-full text-white text-xs">
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            <span>
                              {videoDurationSec !== undefined && !isNaN(videoDurationSec)
                                ? formatTime(videoDurationSec)
                                : '00:00'}
                            </span>
                          </div>
                        </div>
                      </div>
                      <CardContent className="p-4 space-y-3">
                        <div>
                          <h3 className="font-semibold text-slate-900 mb-1 line-clamp-1">{title}</h3>
                          <div className="flex items-center justify-between text-xs text-slate-500">
                            <div className="flex items-center gap-2">
                              <FileText className="w-3 h-3" />
                              <span>{slideCount} slides</span>
                            </div>
                            <div>
                              <span>{displayDate}</span>
                            </div>
                          </div>
                        </div>
                        <Button
                          onClick={() => handleWatchWithChat(video)}
                          className="w-full bg-slate-900 text-white hover:bg-slate-800"
                        >
                          <MessageSquare className="w-4 h-4 mr-2" />
                          Watch & Chat
                        </Button>
                      </CardContent>
                    </Card>
                  );
                })
              ) : (
                <div className="text-center py-12 col-span-full">
                  <Video className="w-16 h-16 mx-auto text-slate-300 mb-4" />
                  <h3 className="text-slate-900 mb-2">No videos found</h3>
                  <p className="text-slate-500">Try adjusting your search query</p>
                </div>
              )}
            </div>
            {!showAllVideos && filteredVideos.length > visibleVideos.length && (
              <div className="mt-2 text-right">
                <button
                  type="button"
                  onClick={() => setShowAllVideos(true)}
                  className="text-sm text-slate-600 underline hover:text-slate-900"
                >
                  +{filteredVideos.length - visibleVideos.length} more
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {selectedVideo && (
        <VideoPlayer
          slides={selectedVideo.slides || []}
          videoUrl={selectedVideo.videoUrl}
          docId={selectedVideo.latest_basename || selectedVideo.basename || selectedVideo.name?.replace(/\.[^/.]+$/, '')}
          onClose={handleCloseVideo}
        />
      )}
    </div>
  );
}