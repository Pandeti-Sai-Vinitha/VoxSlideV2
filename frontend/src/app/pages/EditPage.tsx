import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Save,
  RotateCw,
  ArrowRight,
  CheckCircle,
  Loader,
  Play,
  FileText,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { ScrollArea } from '../components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';

import type { Document, Slide } from '../App';

const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

interface EditPageProps {
  onUpdate: (id: string, updates: Partial<Document>) => void;
  getDocument?: (id: string) => Document | null;
}

type SlideWithImage = Slide & {
  imageUrl?: string;
  imageIndex?: number | null;
  imagePrompt?: string;
};

interface Voice {
  id: string;
  name: string;
  gender?: string;
  description?: string;
}

export default function EditPage({ onUpdate, getDocument }: EditPageProps) {
  const navigate = useNavigate();
  const location = useLocation();

  let document = location.state?.document as Document | undefined;
  if (!document && getDocument) {
    const parts = location.pathname.split('/');
    const possibleId = parts.length > 2 ? parts[parts.length - 1] : undefined;
    if (possibleId) document = getDocument(possibleId) || undefined;
  }

  const [slides, setSlides] = useState<SlideWithImage[]>([]);
  const [selectedSlideId, setSelectedSlideId] = useState<string>('');
  const [hasChanges, setHasChanges] = useState(false);
  const [isRegeneratingAudio, setIsRegeneratingAudio] = useState<string | null>(null);
  const [documentBasename, setDocumentBasename] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [availableSlideImages, setAvailableSlideImages] = useState<{ url: string; label: string }[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string | null>(null);
  const [audioGenerationStatus, setAudioGenerationStatus] = useState<'pending' | 'generating' | 'completed'>('pending');
  const [isGeneratingAllAudio, setIsGeneratingAllAudio] = useState(false);
  const [showVoiceDialog, setShowVoiceDialog] = useState(false);

  const locationState = location.state as { document?: Document; generationMode?: 'pptx' | 'video' } | null;
  
  const outputType = (document as any).output_type?.toLowerCase() ||
    (document?.generationMode === 'video' ? 'pptx+video' : 'pptx');
  const isVideoMode = outputType.includes('video');
  const isPptxOnlyMode = outputType.includes('pptx') && !isVideoMode;
  const showAudio = isVideoMode;
  const showVoiceoverSection = showAudio || (isPptxOnlyMode && audioGenerationStatus === 'completed');
  const canProcess = showVoiceoverSection;

  useEffect(() => {
    if (!document) return;

    const fetchVoices = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/voices`);
        if (!response.ok) return;
        const data = await response.json();
        setVoices(data.voices || []);
        if (!selectedVoiceId && Array.isArray(data.voices) && data.voices.length > 0) {
          setSelectedVoiceId(data.voices[0].id);
        }
      } catch (error) {
        console.warn('Could not load voices', error);
      }
    };

    fetchVoices();
  }, [document?.basename]);

  // When dialog opens, ensure a default voice is selected (in case voices loaded earlier)
  useEffect(() => {
    if (showVoiceDialog && !selectedVoiceId && voices.length > 0) {
      setSelectedVoiceId(voices[0].id);
    }
  }, [showVoiceDialog, selectedVoiceId, voices]);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioDuration, setAudioDuration] = useState(0);
  const [audioCurrentTime, setAudioCurrentTime] = useState(0);

  const toAbsoluteUrl = (url: string) => (url.startsWith('http') ? url : `${API_BASE}${url}`);

  const appendCacheBuster = (url: string) => {
    const absolute = toAbsoluteUrl(url);
    const separator = absolute.includes('?') ? '&' : '?';
    return `${absolute}${separator}t=${Date.now()}`;
  };

  useEffect(() => {
    if (!document) return;

    const loadSlides = async () => {
      setIsLoading(true);
      try {
        const basename = document.basename || document.name.replace(/\.[^/.]+$/, '');
        setDocumentBasename(basename);

        const slidesRes = await fetch(`${API_BASE}/api/process/slides/${basename}`);
        if (!slidesRes.ok) throw new Error('Failed to fetch slides');
        const slidesData = await slidesRes.json();

        const audioRes = await fetch(`${API_BASE}/api/preview/audio/${basename}`);
        let audioData: Record<string, string> = {};
        if (audioRes.ok) {
          const rawAudio = await audioRes.json();
          audioData = rawAudio.audio || rawAudio || {};
        }

        const imageRes = await fetch(`${API_BASE}/api/preview/extracted/${basename}`);
        let availableImages: { url: string; label: string }[] = [];
        if (imageRes.ok) {
          const rawImageData = await imageRes.json();
          const imageUrls = rawImageData.slides || [];
          availableImages = imageUrls.map((imageUrl: string, index: number) => ({ url: toAbsoluteUrl(imageUrl), label: `Image ${index + 1}` }));
        }

        setAvailableSlideImages(availableImages);
        console.log('Available slide images:', availableImages);

        const mergedSlides: SlideWithImage[] = (slidesData.slides || []).map((slide: any, index: number) => {
          const slideId = slide.id || String(index + 1);
          const audioUrl = (audioData as Record<string, string>)[slideId] || (audioData as Record<string, string>)[String(index + 1)];
          const finalAudioUrl = audioUrl ? toAbsoluteUrl(audioUrl) : slide.audioUrl;
          const audioScript = slide.audioScript || slide.audio_script || slide.voiceover || '';
          const imageIndexRaw = slide.imageIndex ?? slide.image_index ?? null;
          let imageIndex: number | null = null;
          let imageUrl: string | undefined = undefined;

          if (typeof imageIndexRaw === 'number') imageIndex = imageIndexRaw;
          else if (typeof imageIndexRaw === 'string') {
            const parsed = parseInt(imageIndexRaw, 10);
            if (!isNaN(parsed)) imageIndex = parsed;
            else {
              const found = availableImages.findIndex((ai) => ai.url.endsWith(imageIndexRaw) || ai.url.endsWith(`/${imageIndexRaw}`));
              if (found >= 0) imageIndex = found;
            }
          }

          if (imageIndex !== null && imageIndex >= 0 && imageIndex < availableImages.length) imageUrl = availableImages[imageIndex].url;
          else if (slide.imageUrl) imageUrl = toAbsoluteUrl(slide.imageUrl);

          return {
            id: slideId,
            title: slide.title || '',
            content: slide.content || '',
            audioScript: audioScript,
            audioUrl: finalAudioUrl,
            status: slide.status || 'generated',
            imagePrompt: slide.imagePrompt || slide.image_prompt || '',
            imageIndex: imageIndex,
            imageUrl,
          } as SlideWithImage;
        });

        setSlides(mergedSlides);
        if (mergedSlides.length > 0) setSelectedSlideId(mergedSlides[0].id);
        
        // ✅ Detect if audio was pre-generated during upload (for PPTX-only mode)
        // If all slides have audioUrl, mark as completed
        const allSlidesHaveAudio = mergedSlides.every(slide => !!slide.audioUrl);
        if (allSlidesHaveAudio && mergedSlides.length > 0) {
          setAudioGenerationStatus('completed');
          console.log('✅ Pre-generated audio detected for all slides');
        }
      } catch (err) {
        console.error('Failed to load slides/audio', err);
        toast.error('Failed to load slides');
        setSlides([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadSlides();
  }, [document]);

  const selectedSlide = slides.find((s) => s.id === selectedSlideId);
  const editModeLabel = showAudio ? 'Video preview' : 'PPTX-only preview';

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
      setIsPlaying(false);
    }
  }, [selectedSlideId]);

  const selectedVoice = voices.find((voice) => voice.id === selectedVoiceId);

  const updateSlideLocal = (slideId: string, updates: Partial<Slide>) => {
    setSlides((prev) => prev.map((s) => (s.id === slideId ? { ...s, ...updates } : s)));
    setHasChanges(true);
    if (isPptxOnlyMode && updates.audioScript !== undefined) {
      setAudioGenerationStatus('pending');
    }
  };

  const handleSaveChanges = async () => {
    if (!document) return;
    try {
      for (const slide of slides) {
        await fetch(`${API_BASE}/api/slides/edit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            document_basename: documentBasename,
            slide_number: Number(slide.id),
            title: slide.title,
            content: slide.content,
            audio_script: slide.audioScript,
            image_index: slide.imageIndex ?? null,
            image_prompt: slide.imagePrompt ?? null,
          }),
        });
      }

      onUpdate(String(document.id), { slides });
      setHasChanges(false);
      toast.success('Slides saved');
    } catch {
      toast.error('Save failed');
    }
  };

  const handleRegenerateAudio = async (slideId: string) => {
    const slide = slides.find((s) => s.id === slideId);
    if (!slide) return;

    setIsRegeneratingAudio(slideId);
    try {
      const body = {
        document_basename: documentBasename,
        slide_number: Number(slideId),
        audio_script: slide.audioScript,
      } as Record<string, any>;

      if (selectedVoiceId) {
        body.voice_name = selectedVoiceId;
        body.voice = selectedVoiceId;
      }

      console.log('Regenerating slide audio with body:', body);
      const res = await fetch(`${API_BASE}/api/voiceover/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errorText = await res.text().catch(() => 'Audio generation failed');
        throw new Error(errorText || 'Audio generation failed');
      }

      const json = await res.json();
      console.log('Regenerate response', json);
      updateSlideLocal(slideId, { audioUrl: appendCacheBuster(json.audio_url) });
      toast.success(`Audio regenerated with voice: ${json.voice_name || selectedVoice?.name || selectedVoiceId}`);
    } catch {
      toast.error('Audio regeneration failed');
    } finally {
      setIsRegeneratingAudio(null);
    }
  };

  const handleGenerateAudioForAllSlides = async () => {
    if (!document) return;
    if (!selectedVoiceId) {
      toast.error('Please select a voice first');
      return;
    }

    if (slides.length === 0) {
      toast.error('No slides to generate audio for');
      return;
    }

    setIsGeneratingAllAudio(true);
    setAudioGenerationStatus('generating');

    try {
      console.log('Generating audio for all slides with voice:', selectedVoiceId);
      const generatedSlides: SlideWithImage[] = [];

      for (const slide of slides) {
        const audioScript = (slide.audioScript || `${slide.title}\n\n${slide.content}`).trim();
        if (!audioScript) {
          throw new Error(`Slide ${slide.id} has no voiceover text.`);
        }

        const requestBody = {
          document_basename: documentBasename,
          slide_number: Number(slide.id),
          audio_script: audioScript,
          voice_name: selectedVoiceId,
          voice: selectedVoiceId,
        };

        const res = await fetch(`${API_BASE}/api/voiceover/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody),
        });
        console.log('Requested voice generation for slide', slide.id, 'with body:', requestBody);

        if (!res.ok) {
          const message = await res.text().catch(() => 'Audio generation failed');
          throw new Error(message || 'Audio generation failed');
        }

        const json = await res.json();
        console.log('Generate all slides response for slide', slide.id, json);
        generatedSlides.push({
          ...slide,
          audioUrl: appendCacheBuster(json.audio_url),
        });
      }

      setSlides(generatedSlides);
      setAudioGenerationStatus('completed');
      setShowVoiceDialog(false);
      toast.success(`Audio generated for all slides with voice: ${selectedVoice?.name || selectedVoiceId}. Click Process to generate video.`);
    } catch (error) {
      console.error('Failed to generate audio for all slides', error);
      toast.error('Audio generation failed');
      setAudioGenerationStatus('pending');
    } finally {
      setIsGeneratingAllAudio(false);
    }
  };

  const handlePlayPreview = () => {
    if (!selectedSlide?.audioUrl) return;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    const audio = new Audio(selectedSlide.audioUrl);
    audioRef.current = audio;
    audio.addEventListener('loadedmetadata', () => setAudioDuration(audio.duration));
    audio.addEventListener('timeupdate', () => setAudioCurrentTime(audio.currentTime));
    audio.addEventListener('ended', () => {
      setIsPlaying(false);
      setAudioCurrentTime(0);
      audioRef.current = null;
    });
    audio.play().then(() => setIsPlaying(true)).catch(() => toast.error('Unable to play audio'));
  };

  const handlePausePreview = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const [isProcessing, setIsProcessing] = useState(false);

  // ✅ ✅ ADD THIS BLOCK RIGHT HERE
  useEffect(() => {
    if (!isProcessing) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/documents`);
        const data = await res.json();

        const doc = data.items.find(
          (d: any) => d.basename === documentBasename
        );

        if (doc?.status === 'completed') {
          clearInterval(interval);

          toast.success('Processing complete! ✅');

          onUpdate(String(document?.id), {
            status: 'completed',
          });

          navigate(`/results/${document?.id}`);
        }

        if (doc?.status === 'failed') {
          clearInterval(interval);
          toast.error('Processing failed ❌');
          setIsProcessing(false);
        }

      } catch (e) {
        console.error('Polling error', e);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [isProcessing]);

  const handleProcess = async () => {
    if (hasChanges) {
      toast.error('Save changes before processing');
      return;
    }

    if (!documentBasename) {
      toast.error('Missing document basename');
      return;
    }

    setIsProcessing(true);

    // ✅ Set status to processing locally
    onUpdate(String(document?.id), {
      status: 'processing',
    });

    try {
      const res = await fetch(`${API_BASE}/api/process/generate-media`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_basename: documentBasename }),
      });

      if (!res.ok) {
        throw new Error('Processing failed');
      }

      // ✅ Only acknowledge start (NOT completion)
      await res.json();

      toast.info('Processing started — please wait...');

      // ❌ DO NOT navigate here
      // ❌ DO NOT set completed here

    } catch (err) {
      console.error(err);
      toast.error('Processing failed');

      onUpdate(String(document?.id), {
        status: 'failed',
      });

      setIsProcessing(false);
    }
  };

  if (!document || isLoading) {
    return (
      <div className="p-12 text-center">
        <Loader className="animate-spin mx-auto mb-3" size={32} />
        <p className="text-slate-600">Loading…</p>
      </div>
    );
  }

  if (!selectedSlide) {
    return (
      <div className="p-12 text-center">
        <FileText className="w-12 h-12 mx-auto text-slate-300 mb-4" />
        <p className="text-slate-600">No slides available</p>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-slate-50 via-indigo-50/40 to-purple-100/40">
      <div className="px-8 py-6 flex-1 min-h-0 flex flex-col">
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-lg p-4 text-white shadow-md mb-8">
          <div className="max-w-7xl mx-auto flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-semibold text-white tracking-wide">{document.name}</h1>
              <p className="text-sm text-indigo-100">{slides.length} slides • {editModeLabel}</p>
            </div>
            <div className="flex gap-3 items-center">
              <Button variant="outline" disabled={!hasChanges} onClick={handleSaveChanges} className="bg-white text-indigo-700 font-semibold shadow-md hover:shadow-lg">
                <Save className="w-4 h-4 mr-2" /> Save
              </Button>
              {isGeneratingAllAudio && (
                <Button disabled className="bg-white text-indigo-700 font-semibold shadow-md hover:shadow-lg opacity-75">
                  <Loader className="w-4 h-4 mr-2 animate-spin" /> Generating…
                </Button>
              )}
              {!isGeneratingAllAudio && isPptxOnlyMode && audioGenerationStatus !== 'completed' && (
                <Button onClick={() => setShowVoiceDialog(true)} className="bg-white text-indigo-700 font-semibold shadow-md hover:shadow-lg">
                  Generate Voice
                </Button>
              )}
              {!isGeneratingAllAudio && isVideoMode && audioGenerationStatus === 'completed' && (
                <Button onClick={() => setShowVoiceDialog(true)} className="bg-white text-indigo-700 font-semibold shadow-md hover:shadow-lg" variant="outline">
                  Change Voice
                </Button>
              )}
              {!isGeneratingAllAudio && canProcess && (
                <Button onClick={handleProcess} disabled={isProcessing} className="bg-white text-indigo-700 font-semibold shadow-md hover:shadow-lg">
                  {isProcessing ? (
                    <>
                      <Loader className="w-4 h-4 mr-2 animate-spin" />
                      Processing…
                    </>
                  ) : (
                    <>
                      Process <ArrowRight className="w-4 h-4 ml-2" />
                    </>
                  )}
                </Button>
              )}
              <Button
                variant="outline"
                disabled={!documentBasename}
                onClick={() => {
                  const folder = documentBasename;
                  const filename = documentBasename;
                  const url = `${API_BASE}/api/download/pptx/${encodeURIComponent(folder)}/${encodeURIComponent(filename)}`;
                  const link = window.document.createElement('a');
                  link.href = url;
                  link.download = `${filename}.pptx`;
                  window.document.body.appendChild(link);
                  link.click();
                  link.remove();
                }}
                className="bg-white text-indigo-700 font-semibold shadow-md hover:shadow-lg"
              >
                <ArrowRight className="w-4 h-4 mr-2 rotate-90" /> Download PPTX
              </Button>

              <div className="ml-3 flex items-center gap-3">
                <Button variant="ghost" size="sm" className="text-white border-white/30 hover:border-white/50" onClick={() => navigate('/library')}>
                  Back to library
                </Button>
              </div>
            </div>
          </div>
        </div>

        <Dialog open={showVoiceDialog} onOpenChange={(open) => !isGeneratingAllAudio && setShowVoiceDialog(open)}>
          <DialogContent className="sm:max-w-5xl">
            <DialogHeader>
              <DialogTitle>Select Voice for All Slides</DialogTitle>
              <DialogDescription>
                Pick a voice, then click Generate to create audio for every slide.
              </DialogDescription>
            </DialogHeader>

            {isGeneratingAllAudio && (
              <div className="flex flex-col items-center justify-center py-12 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-lg border border-indigo-200 gap-3">
                <Loader className="w-8 h-8 text-indigo-600 animate-spin" />
                <div className="text-center">
                  <p className="text-base font-semibold text-slate-800">Generating audio for all slides…</p>
                  <p className="text-sm text-slate-600 mt-2">This may take a couple of minutes. Please wait.</p>
                </div>
              </div>
            )}

            {!isGeneratingAllAudio && (
              <div className="space-y-3 py-4">
                {voices.length === 0 ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader className="w-4 h-4 text-indigo-600 animate-spin mr-2" />
                    <span className="text-sm text-slate-600">Loading voices…</span>
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-3 gap-3">
                    {voices.map((voice) => (
                      <button
                        key={voice.id}
                        type="button"
                        onClick={() => setSelectedVoiceId(voice.id)}
                        className={`p-3 rounded-lg text-left border transition-all duration-200 ${
                          selectedVoiceId === voice.id
                            ? 'border-indigo-600 bg-indigo-50 text-indigo-900 shadow-md'
                            : 'border-slate-200 bg-white text-slate-800 hover:border-indigo-300 hover:bg-slate-50'
                        }`}
                      >
                        <div className="font-semibold text-sm leading-tight">{voice.name}</div>
                        <p className="text-xs text-slate-600 mt-1 line-clamp-1">{voice.description}</p>
                        <p className="text-[11px] text-slate-500 mt-1">{voice.gender}</p>
                      </button>
                    ))}
                  </div>
                  </>
                )}
              </div>
            )}

            <DialogFooter className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowVoiceDialog(false)} disabled={isGeneratingAllAudio}>
                Cancel
              </Button>
              <Button
                onClick={handleGenerateAudioForAllSlides}
                disabled={isGeneratingAllAudio || !selectedVoiceId || voices.length === 0}
              >
                {isGeneratingAllAudio ? (
                  <>
                    <Loader className="w-4 h-4 mr-2 animate-spin" />
                    Generating…
                  </>
                ) : (
                  'Generate'
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <div className="flex flex-1 min-h-0 overflow-hidden">
          <div className="w-80 min-h-0 bg-white border-r border-slate-200 shadow-sm flex flex-col">
            <ScrollArea className="h-full min-h-0">
              <div className="p-4 flex flex-col gap-3">
                {slides.map((slide, index) => (
                  <button
                    key={slide.id}
                    onClick={() => setSelectedSlideId(slide.id)}
                    className={`w-full p-4 rounded-xl border transition-all duration-200 text-left ${
                      slide.id === selectedSlideId
                        
                        ? 'border-indigo-500 bg-indigo-50 shadow-md scale-[1.02]'
                        : 'border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'

                    }`}
                  >
                    <div className="flex justify-between items-center text-xs text-slate-500 mb-1">
                      <span className="font-medium">Slide {index + 1}</span>
                      {slide.status === 'generated' && (
                        <CheckCircle className="w-4 h-4 text-emerald-600" />
                      )}
                    </div>

                    <div className="font-medium text-slate-900 line-clamp-2 mt-1">
                      {slide.title || 'Untitled Slide'}
                    </div>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </div>

          <div className="flex-1 min-h-0">
            <ScrollArea className="h-full min-h-0 p-10">
              <div className="max-w-4xl mx-auto space-y-8">
                <Card className="bg-white/90 backdrop-blur-xl shadow-xl border border-slate-200 rounded-2xl">
                  <CardHeader className="bg-gradient-to-r from-indigo-50 to-purple-100 border-b border-slate-200 rounded-t-2xl">
                    <CardTitle className="text-lg font-semibold text-slate-800">Slide Content</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Label>Title</Label>
                    <Textarea rows={2} className="bg-white border border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 rounded-lg" value={selectedSlide.title} onChange={(e) => updateSlideLocal(selectedSlide.id, { title: e.target.value })} />

                    <Label>Content</Label>
                    <Textarea rows={5} className="bg-white border border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 rounded-lg" value={selectedSlide.content} onChange={(e) => updateSlideLocal(selectedSlide.id, { content: e.target.value })} />

                    <div>
                      <Label>Slide Image</Label>
                      <div className="mt-2 flex items-start gap-4">
                        {selectedSlide.imageUrl ? (
                          <img src={selectedSlide.imageUrl} alt="slide" className="w-48 h-32 object-cover rounded-lg border" />
                        ) : (
                          <div className="w-48 h-32 bg-slate-100 rounded-lg border flex items-center justify-center text-sm text-slate-500">No image</div>
                        )}

                        <div className="flex-1">
                          <div className="flex gap-2 mb-2">
                            <Button variant="outline" size="sm" onClick={() => updateSlideLocal(selectedSlide.id, { imageIndex: null, imageUrl: undefined })}>Remove Image</Button>
                            <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>Add Image</Button>
                          </div>

                          <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            className="hidden"
                            onChange={async (e) => {
                              const f = e.target.files?.[0];
                              if (!f) return;
                              const form = new FormData();
                              form.append('file', f);
                              try {
                                const upRes = await fetch(`${API_BASE}/api/preview/extracted/${documentBasename}/upload`, {
                                  method: 'POST',
                                  body: form,
                                });
                                if (!upRes.ok) throw new Error('Upload failed');
                                const upJson = await upRes.json();

                                const imagesRes = await fetch(`${API_BASE}/api/preview/extracted/${documentBasename}`);
                                const rawImages = imagesRes.ok ? await imagesRes.json() : { slides: [] };
                                const imageUrls = rawImages.slides || [];
                                const availableImages = imageUrls.map((imageUrl: string, index: number) => ({ url: toAbsoluteUrl(imageUrl), label: `Image ${index + 1}` }));
                                setAvailableSlideImages(availableImages);

                                const newFilename = upJson.filename;
                                const newIndex = imageUrls.findIndex((u: string) => u.endsWith(newFilename));
                                if (newIndex >= 0) updateSlideLocal(selectedSlide.id, { imageIndex: newIndex, imageUrl: availableImages[newIndex].url });
                                toast.success('Image uploaded');
                              } catch (err) {
                                console.error(err);
                                toast.error('Image upload failed');
                              } finally {
                                if (fileInputRef.current) fileInputRef.current.value = '';
                              }
                            }}
                          />

                          <Label>Choose Alternate Image</Label>
                          <div className="mt-2 grid grid-cols-4 gap-2">
                            {availableSlideImages.map((img, idx) => (
                              <button key={img.url} onClick={() => updateSlideLocal(selectedSlide.id, { imageIndex: idx, imageUrl: img.url })} className={`w-full h-20 rounded-lg overflow-hidden border ${selectedSlide.imageIndex === idx ? 'border-indigo-500' : 'border-slate-200'}`}>
                                <img src={img.url} alt={img.label} className="w-full h-full object-cover" />
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {showVoiceoverSection && (
                  <Card className="bg-white/90 backdrop-blur-xl shadow-xl border border-slate-200 rounded-2xl">
                    <CardHeader className="bg-gradient-to-r from-indigo-50 to-purple-100 border-b border-slate-200 rounded-t-2xl">
                      <CardTitle className="text-lg font-semibold text-slate-800">Voiceover</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <Label>Audio Script</Label>
                      <Textarea rows={4} className="bg-white border border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 rounded-lg" value={selectedSlide.audioScript} onChange={(e) => updateSlideLocal(selectedSlide.id, { audioScript: e.target.value })} />

                      <Label>Audio Preview</Label>
                      <div className="flex items-center gap-4 p-4 bg-gradient-to-br from-indigo-50 to-purple-100 rounded-xl border border-indigo-200 shadow-sm">
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm" disabled={!selectedSlide.audioUrl || !isPlaying} onClick={handlePausePreview} className="bg-red-50 border-red-200 text-red-700 hover:bg-red-100">⏸</Button>
                          <Button variant="outline" size="sm" disabled={!selectedSlide.audioUrl || isPlaying} onClick={handlePlayPreview} className="bg-green-50 border-green-200 text-green-700 hover:bg-green-100"><Play className="w-4 h-4 mr-2" />Play</Button>
                        </div>
                        <div className="flex-1 h-2 bg-indigo-100 rounded-full overflow-hidden shadow-inner">
                          <div className={`h-full transition-all ${isPlaying ? 'bg-gradient-to-r from-indigo-600 to-purple-600' : 'bg-indigo-400'}`} style={{ width: `${audioDuration ? (audioCurrentTime / audioDuration) * 100 : 0}%` }} />
                        </div>
                        <div className="text-sm font-mono text-slate-700 min-w-[50px] text-right">{formatTime(audioCurrentTime)} / {formatTime(audioDuration)}</div>
                      </div>

                      <Button className="bg-indigo-600 text-white hover:bg-indigo-700 shadow-md" onClick={() => handleRegenerateAudio(selectedSlide.id)} disabled={isRegeneratingAudio === selectedSlide.id}>
                        {isRegeneratingAudio ? (<><Loader className="w-4 h-4 mr-2 animate-spin" />Regenerating</>) : (<><RotateCw className="w-4 h-4 mr-2" />Regenerate Audio</>)}
                      </Button>
                    </CardContent>
                  </Card>
                )}
              </div>
            </ScrollArea>
          </div>
        </div>
      </div>
    </div>
  );
}