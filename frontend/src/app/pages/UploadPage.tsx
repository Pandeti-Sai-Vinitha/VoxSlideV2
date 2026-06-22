import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Upload, FileText, CheckCircle, X, Loader, ChevronDown, Play, Pause, Volume2, Plus, Trash2, Image as ImageIcon, Edit2, Target, RefreshCcw, Layers, Users, BarChart3, Mic, User, Clock } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { designTokens } from '../design-system';
import type { Document, Slide } from '../App';

interface DocBlock {
  id: string;
  type: 'h1' | 'h2' | 'paragraph' | 'image';
  content: string;
  imageUrl?: string;
}

interface ExtractedImage {
  id: string;
  url: string;
  caption: string;
}

interface ExtractedBlock {
  id: string;
  type: 'h1' | 'h2' | 'paragraph' | 'image';
  content?: string;
  imageUrl?: string;
  children?: ExtractedBlock[];
}

type ExtractedContentResponse = {
  blocks?: ExtractedBlock[];
  images?: string[];
};

interface ExistingDoc {
  basename?: string;
  name: string;
  [key: string]: unknown;
}

interface Voice {
  id: string;
  name: string;
  gender: string;
  description: string;
}

interface Persona {
  id: string;
  name: string;
  emoji: string;
  description: string;
  icon: string;
  default_slides: number;
  min_slides: number;
  max_slides: number;
}

interface TemplateOption {
  name: string;
  previewUrl?: string;
}

const resolveApiBase = () => {
  const raw = (import.meta as any).env?.VITE_API_BASE_URL || (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
  if (typeof raw !== 'string' || !raw.trim()) return 'http://localhost:8000';
  if (raw.startsWith(':')) return `http://localhost${raw}`;
  if (raw.startsWith('//')) return `http:${raw}`;
  return raw.replace(/\/$/, '');
};

async function updateDocumentStatus(documentId: string, status: string) {
  const API_BASE = resolveApiBase();
  await fetch(`${API_BASE}/api/documents/${documentId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(status)
  });
}

interface UploadPageProps {
  onUpload: (doc: Document) => void;
}

export default function UploadPage({ onUpload }: UploadPageProps) {
  const navigate = useNavigate();
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStage, setProcessingStage] = useState('');
  const [logs, setLogs] = useState<string[]>([]);
  const [logBasename, setLogBasename] = useState<string>('');
  const [pdfBasename, setPdfBasename] = useState<string>('');
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string>('');
  const [templates, setTemplates] = useState<TemplateOption[]>([
    { name: 'Sample.pptx' },
    { name: 'Sample1.pptx' }
  ]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('Sample.pptx');
  const [loadingVoices, setLoadingVoices] = useState(true);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<string>('');
  const [personaPhase, setPersonaPhase] = useState<'selectPersona' | 'selectSlides' | 'selectVoice'>('selectPersona');
  const [domainPhase, setDomainPhase] = useState<'selectDomain' | 'selectOutput' | 'selectVoice'>('selectDomain');
  const domainOptions = ['Financial Services', 'Banking'];
  const [selectedDomain, setSelectedDomain] = useState<string>('');
  const [promptInstructions, setPromptInstructions] = useState<string>('');
  const [loadingPersonas, setLoadingPersonas] = useState(true);
  const [isVoiceMinimized, setIsVoiceMinimized] = useState(false);
  const [isPersonaMinimized, setIsPersonaMinimized] = useState(false);
  const [selectedSlideCount, setSelectedSlideCount] = useState<number>(8);
  const [outputMode, setOutputMode] = useState<'pptx' | 'video'>('pptx');
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [loadingVoicePreview, setLoadingVoicePreview] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState<'upload' | 'template' | 'domain' | 'persona' | 'processing'>('upload');
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const pollerRef = useRef<number | null>(null);
  const [showLogs, setShowLogs] = useState(false);

  useEffect(() => {
    if (activeStep === 'persona') {
      setPersonaPhase('selectPersona');
    }
  }, [activeStep]);

  useEffect(() => {
    if (activeStep === 'domain') {
      setDomainPhase('selectDomain');
    }
  }, [activeStep]);

  useEffect(() => {
    if (outputMode === 'pptx') {
      setSelectedVoice('');
    }
  }, [outputMode]);

  // Existing project regeneration state
  const location = useLocation();
  const [existingDoc, setExistingDoc] = useState<any>(null);

  // Document editing state
  const [showEditPanel, setShowEditPanel] = useState(false);
  const [blocks, setBlocks] = useState<DocBlock[]>([]);
  const [extractedImages, setExtractedImages] = useState<ExtractedImage[]>([]);
  const [showImageLibrary, setShowImageLibrary] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const [activeImageBlock, setActiveImageBlock] = useState<string | null>(null);

  // Auto-detect existing project from navigation state
  useEffect(() => {
  const editDoc = (location.state as any)?.editDocument;

  if (editDoc) {
    setExistingDoc(editDoc);
    setActiveStep('template');

    // ✅ ✅ IMPORTANT: CLEAR STATE
    window.history.replaceState({}, document.title);
  }
}, [location.state]);

  // Prefill settings when coming from a specific version (reconfigure)
  useEffect(() => {
    const versionConfig = (location.state as any)?.versionConfig;
    if (versionConfig) {
      if (versionConfig.template) setSelectedTemplate(versionConfig.template);
      if (versionConfig.persona) setSelectedPersona(versionConfig.persona);
      if (versionConfig.voice) setSelectedVoice(versionConfig.voice);
      // Support both `slides` and `slides_count` keys from different sources
      if (typeof versionConfig.slides === 'number') setSelectedSlideCount(versionConfig.slides);
      else if (typeof versionConfig.slides_count === 'number') setSelectedSlideCount(versionConfig.slides_count);
      // Keep user on template step for adjustments
      setActiveStep('template');
      // Clear navigation state to avoid double-prefill
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  // Helper function to check if a step can be navigated to
  const canNavigateToStep = (targetStep: 'upload' | 'template' | 'domain' | 'persona' | 'processing'): boolean => {
    const steps = ['upload', 'template', 'persona', 'domain', 'processing'] as const;
    const currentStepIndex = steps.indexOf(activeStep);
    const targetStepIndex = steps.indexOf(targetStep);

    const hasSource = uploadedFile !== null || existingDoc !== null;
    if (targetStep === 'upload') return true;
    if (targetStep === 'template') return hasSource;
    if (targetStep === 'persona') return hasSource && !!selectedTemplate;
    if (targetStep === 'domain') return hasSource && !!selectedPersona;
    if (targetStep === 'processing') return false;
    if (targetStepIndex <= currentStepIndex) return hasSource;
    if (targetStepIndex === currentStepIndex + 1) return hasSource;
    return false;
  };

  // Helper function to navigate to a step
  const navigateToStep = (step: 'upload' | 'template' | 'domain' | 'persona' | 'processing') => {
    if (canNavigateToStep(step)) {
      setActiveStep(step);
    }
  };

  const allSteps = ['upload', 'template', 'persona', 'domain', 'processing'] as const;
  const visibleSteps = allSteps;
  const currentActiveStep = activeStep;
  const selectedPersonaObj = personas.find((persona) => persona.id === selectedPersona);
  const isTraineePersona = selectedPersonaObj?.name.toLowerCase().includes('trainee') || false;

  // Document editing functions
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeImageBlock) return;

    const imageUrl = URL.createObjectURL(file);
    setBlocks(prev =>
      prev.map(b =>
        b.id === activeImageBlock
          ? { ...b, imageUrl }
          : b
      )
    );
    e.target.value = "";
  };

  const loadExtractedContent = async (file: File) => {
    try {
      const API_BASE = resolveApiBase();
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_BASE}/api/studio/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");

      const data = await res.json();

      // Process blocks with images
      const blocksWithImages = [];
      let imageIndex = 0;

      for (let i = 0; i < data.blocks.length; i++) {
        const block = data.blocks[i];

        if (block.type === "image") {
          blocksWithImages.push({
            ...block,
            imageUrl: data.images?.[imageIndex]
              ? (data.images[imageIndex].startsWith("http")
                  ? data.images[imageIndex]
                  : `${API_BASE}/${data.images[imageIndex]}`)
              : ""
          });
          imageIndex++;
        } else {
          blocksWithImages.push(block);
        }
      }

      setBlocks(blocksWithImages);

      // Process extracted images
      const images: ExtractedImage[] = (data.images || []).map(
        (path: string, idx: number) => ({
          id: `img_${idx}`,
          url: path.startsWith("http")
            ? path
            : `${API_BASE}/${path}`,
          caption: `Image ${idx + 1}`,
        })
      );

      setExtractedImages(images);
      setShowEditPanel(true);
    } catch (err) {
      console.error(err);
      toast.error("Failed to load document content");
    }
  };

  const updateBlock = (id: string, content: string) =>
    setBlocks(bs => bs.map(b => b.id === id ? { ...b, content } : b));

  const removeBlock = (id: string) =>
    setBlocks(bs => bs.filter(b => b.id !== id));

  const changeType = (id: string, type: DocBlock['type']) =>
    setBlocks(bs => bs.map(b =>
      b.id === id ? { ...b, type, content: type === 'image' ? '' : b.content } : b
    ));

  const addBlock = (afterId: string, type: DocBlock['type'], customId?: string) => {
    const idx = blocks.findIndex(b => b.id === afterId);
    const id = customId || `b${Date.now()}`;

    const next = [...blocks];
    next.splice(idx + 1, 0, {
      id,
      type,
      content: '',
      imageUrl: ''
    });

    setBlocks(next);
  };

  const updateBlockImage = (id: string, imageUrl: string) =>
    setBlocks(bs => bs.map(b => b.id === id ? { ...b, imageUrl } : b));

  useEffect(() => {
    const fetchOptions = async () => {
      try {
        const API_BASE = resolveApiBase();

        const voiceResponse = await fetch(`${API_BASE}/api/voices`);
        if (voiceResponse.ok) {
          const data = await voiceResponse.json();
          setVoices(data.voices);
          if (data.voices.length > 0) {
            setSelectedVoice(data.voices[0].id);
          }
        }

        const personaResponse = await fetch(`${API_BASE}/api/personas`);
        if (personaResponse.ok) {
          const data = await personaResponse.json();
          const allowedPersonas = [
            "Trainee / Maverick",
            "Technical Expert",
            "Business Analyst",
            "Executive"
          ];
          const filteredPersonas = data.personas.filter((persona: Persona) =>
            allowedPersonas.includes(persona.name)
          );
          setPersonas(filteredPersonas);
          if (filteredPersonas.length > 0) {
            const firstPersona = filteredPersonas[0];
            setSelectedPersona(firstPersona.id);
            setSelectedSlideCount(firstPersona.default_slides);
          }
        }

        const templateRes = await fetch(`${API_BASE}/api/process/templates`);
        if (templateRes.ok) {
          const data = await templateRes.json();
          if (Array.isArray(data.templates) && data.templates.length > 0) {
            const resolvedTemplates = data.templates.map((template: TemplateOption) => ({
              ...template,
              previewUrl: template.previewUrl ? `${API_BASE}${template.previewUrl}` : undefined,
            }));
            setTemplates(resolvedTemplates);
            setSelectedTemplate(resolvedTemplates[0].name);
          }
        }
      } catch (err) {
        console.error('Failed to fetch options:', err);
        toast.error('Could not load options');
      } finally {
        setLoadingVoices(false);
        setLoadingPersonas(false);
      }
    };

    fetchOptions();

    return () => {
      if (pollerRef.current) {
        clearInterval(pollerRef.current);
      }
    };
  }, []);

  const waitForSlidesReady = async (
    basename: string,
    attempts = 5,
    intervalMs = 2500
  ) => {
    const API_BASE = resolveApiBase();
    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= attempts; attempt++) {
      try {
        const response = await fetch(
          `${API_BASE}/api/slides/${encodeURIComponent(basename)}`
        );
        if (response.ok) {
          const data = await response.json();
          if (Array.isArray(data.slides) && data.slides.length > 0) {
            return data;
          }
        }
      } catch (err) {
        lastError = err instanceof Error ? err : new Error('Unknown slide check error');
      }

      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }

    throw lastError || new Error('Slides were not ready in time');
  };

  const navigateToEditPage = (doc: Document) => {
    const targetPath = `/edit/${encodeURIComponent(doc.id)}`;
    navigate(targetPath, { state: { document: doc } });

    if (window.location.pathname !== targetPath) {
      window.setTimeout(() => {
        if (window.location.pathname !== targetPath) {
          window.location.href = targetPath;
        }
      }, 300);
    }
  };

  // Auto-scroll logs to bottom when they update
  useEffect(() => {
    if (showLogs && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, showLogs]);

  const startStreamingLogs = (basename: string): Promise<void> => {
    const API_BASE = resolveApiBase();

    return new Promise((resolve) => {
      if (pollerRef.current) {
        clearInterval(pollerRef.current);
      }

      const uploadStartTime = Date.now() / 1000;
      let seenInitialLogs = false;
      let lastLogCount = 0;

      pollerRef.current = window.setInterval(async () => {
        const res = await fetch(
          `${API_BASE}/api/status/logs/${encodeURIComponent(basename)}`
        );
        const data = await res.json();

        if (data.logs) {
          const hasNewLogs = data.logs.length > lastLogCount;
          if (hasNewLogs || data.logs.length > 0) {
            seenInitialLogs = seenInitialLogs || data.logs.length > 0;
            lastLogCount = data.logs.length;
            setLogs(data.logs);
          }

          if (seenInitialLogs && data.logs.some((log: string) =>
            log.toLowerCase().includes("pipeline completed successfully") ||
            (log.toLowerCase().includes("completed") && log.toLowerCase().includes("awaiting"))
          )) {
            if (pollerRef.current) {
              clearInterval(pollerRef.current);
              pollerRef.current = null;
            }
            resolve();
          }
        }
      }, 2000);
    });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    validateAndSetFile(file);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      validateAndSetFile(file);
    }
  };

  const validateAndSetFile = (file: File) => {
    const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!validTypes.includes(file.type)) {
      setError('Please upload a PDF or DOCX file only.');
      setUploadedFile(null);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB.');
      setUploadedFile(null);
      return;
    }
    setError('');
    setUploadedFile(file);
    setActiveStep('template');
  };

  const handleSelectPersona = (personaId: string) => {
    setSelectedPersona(personaId);
    const persona = personas.find(p => p.id === personaId);
    if (persona) {
      setSelectedSlideCount(persona.default_slides);
    }
    setSelectedDomain('');
    setOutputMode('pptx');
    setSelectedVoice('');
    setPersonaPhase('selectSlides');
  };

  const handleSelectSlideCount = (count: number) => {
    setSelectedSlideCount(count);
  };

  const handleSlideCountDone = () => {
    setActiveStep('domain');
  };

  const handleSelectOutputMode = (mode: 'pptx' | 'video') => {
    setOutputMode(mode);
    if (mode === 'video') {
      setDomainPhase('selectVoice');
    }
  };

  const handlePersonaContinue = () => {
    setActiveStep('domain');
  };

  const handleSelectVoice = (voiceId: string) => {
    setSelectedVoice(voiceId);
  };

const flattenBlocks = (blocks: ExtractedBlock[]): DocBlock[] => {
  const result: DocBlock[] = [];

  const traverse = (block: ExtractedBlock) => {
    result.push({
      id: block.id,
      type: block.type,
      content: block.content || "",
      imageUrl: block.imageUrl || ""
    });

    if (block.children && block.children.length > 0) {
      block.children.forEach(traverse);
    }
  };

  blocks.forEach(traverse);
  return result;
};
  const loadExtractedContentFromDoc = async (doc: ExistingDoc) => {
  const API_BASE = resolveApiBase();

  let basename =
    doc.basename ||
    doc.name.replace(/\.[^/.]+$/, '');

  console.log(`📂 Loading extracted content for: ${basename}`);
  
  // Fetch directly - backend is smart enough to handle both versioned and non-versioned basenames
  const res = await fetch(
    `${API_BASE}/api/studio/content/${encodeURIComponent(basename)}`
  );

  if (!res.ok) {
    console.warn(`⚠️ Failed to load extracted content: ${res.status}. Basename: ${basename}`);
    setBlocks([]);
    return;
  }

  const data: ExtractedContentResponse = await res.json();

  // ✅ Validate that data has blocks before flattening
  if (!data || !data.blocks) {
    console.warn('⚠️ No blocks found in extracted content');
    setBlocks([]);
    return;
  }

  // ✅ flatten
  const flatBlocks = flattenBlocks(data.blocks);

  // ✅ fix block image URLs
  let imageIndex = 0;

  const processedBlocks = flatBlocks.map(b => {
    if (b.type === "image") {
      const path = data.images?.[imageIndex] ?? '';

      const imageUrl = path
        ? (path.startsWith("http")
            ? path
            : `${API_BASE}/${path.replace(/\\/g, "/")}`)
        : "";

      imageIndex++;

      return {
        ...b,
        imageUrl
      };
    }

    return b;
  });

  setBlocks(processedBlocks);

  // ✅ fix image list URLs
  const images: ExtractedImage[] = (data.images || []).map((path: string, idx: number) => ({
    id: `img_${idx}`,
    url: path.startsWith("http")
      ? path
      : `${API_BASE}/${path.replace(/\\/g, "/")}`,
    caption: `Image ${idx + 1}`
  }));

  setExtractedImages(images);
  setShowEditPanel(true);
};

  const playVoicePreview = async (voiceId: string) => {
    try {
      const API_BASE = resolveApiBase();

      if (playingVoiceId === voiceId && audioRef.current) {
        audioRef.current.pause();
        setPlayingVoiceId(null);
        return;
      }

      if (audioRef.current) {
        audioRef.current.pause();
      }

      setLoadingVoicePreview(voiceId);

      const response = await fetch(`${API_BASE}/api/voices/preview/${voiceId}`);
      if (!response.ok) {
        throw new Error(`Failed to load voice preview: ${response.statusText}`);
      }

      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);

      if (!audioRef.current) {
        audioRef.current = new Audio();
        audioRef.current.onended = () => {
          setPlayingVoiceId(null);
        };
      }

      audioRef.current.src = audioUrl;
      audioRef.current.play();
      setPlayingVoiceId(voiceId);
      setLoadingVoicePreview(null);
    } catch (err) {
      console.error('Failed to play voice preview:', err);
      toast.error('Could not play voice preview. Please try again.');
      setLoadingVoicePreview(null);
    }
  };

  const handleRemoveFile = () => {
    setUploadedFile(null);
    setExistingDoc(null);
    setError('');
    setActiveStep('upload');
    setShowEditPanel(false);
    setBlocks([]);
    setExtractedImages([]);
    setPromptInstructions('');
    setSelectedPersona('');
    setSelectedDomain('');
    setSelectedVoice('');
    setPersonaPhase('selectPersona');
    setOutputMode('pptx');
    setSelectedSlideCount(8);
  };

  const handleUpload = async (domainChoice?: string) => {
    // Must have either a new file or an existing doc to regenerate
    if (!uploadedFile && !existingDoc) return;

    setIsProcessing(true);
    setActiveStep('processing');
    setProcessingStage('Starting...');
    setLogs([]);
    setShowLogs(true);
    console.log("FINAL VALUES SENT:", {
  selectedVoice,
  selectedPersona,
  selectedTemplate,
  selectedSlideCount,
  selectedDomain: domainChoice ?? selectedDomain,
});

    try {
      const API_BASE = resolveApiBase();
      let docId: string;
      let basename: string;
      let filename: string;

      if (existingDoc) {
        // ─── REGENERATION PATH: skip file upload, use existing document ───
        docId = String(existingDoc.id);
        basename = existingDoc.basename || existingDoc.name.replace(/\.[^/.]+$/, '');
        filename = existingDoc.name;
        setProcessingStage('Re-generating presentation from existing document...');
        setPdfBasename(basename);
      } else {
        // ─── NEW UPLOAD PATH ─────────────────────────────────────────────
        basename = uploadedFile!.name.replace(/\.[^/.]+$/, '');
        filename = uploadedFile!.name;
        setPdfBasename(basename);

        setProcessingStage('Saving file to database...');
        const fileFormData = new FormData();
        fileFormData.append('file', uploadedFile!);

        const fileResponse = await fetch(`${API_BASE}/api/process/upload-file`, {
          method: 'POST',
          body: fileFormData
        });

        if (!fileResponse.ok) {
          const errorData = await fileResponse.json().catch(() => ({}));
          throw new Error(errorData.detail || `File save failed: ${fileResponse.statusText}`);
        }

        const fileResult = await fileResponse.json();
        docId = fileResult.document_id;

        if (!docId || typeof docId !== 'string' || docId.length < 10) {
          throw new Error('Invalid document_id received from backend');
        }

        onUpload({
          id: docId,
          name: filename,
          basename,
          fileType: uploadedFile?.type.includes('pdf') ? 'PDF' : 'DOCX',
          status: 'uploading',
          createdDate: new Date().toISOString().split('T')[0],
          size: `${((uploadedFile?.size || 0) / (1024 * 1024)).toFixed(1)} MB`,
          generationMode: outputMode,
          slides: [],
          output_type: outputMode === 'video' ? 'pptx+video' : 'pptx',
        });
      }

      setProcessingStage(outputMode === 'video'
        ? 'Generating slides and audio narration...'
        : 'Generating presentation...');

      // ✅ Step 2a: For existing documents, get next version
      let versionedBasename = basename;
      if (existingDoc) {
        setProcessingStage('Determining next version...');
        try {
          const versionResponse = await fetch(`${API_BASE}/api/documents/${docId}/new-version`, { method: 'GET' });
          if (versionResponse.ok) {
            const versionData = await versionResponse.json();
            versionedBasename = versionData.basename || versionData.next_basename || versionData.nextBasename || versionData.next || versionedBasename;
            setProcessingStage(`Generating ${versionedBasename}...`);
          }
        } catch (e) {
          console.warn('Version lookup failed, using existing basename', e);
        }
      }

      // ✅ Step 2b: Start generation with JSON payload
      const generatePayload: any = {
        document_id: String(docId),
        persona: selectedPersona,
        domain: domainChoice ?? selectedDomain,
        template: selectedTemplate,
        slides: selectedSlideCount,
        prompt_instructions: promptInstructions,
        mode: outputMode,
        ...(existingDoc && { basename: versionedBasename }) // ✅ Include basename only for versioned docs
      };

      if (outputMode === 'video') {
        generatePayload.voice = selectedVoice;
      }

      console.log('📤 Sending generate request:', generatePayload);

      const genResponse = await fetch(`${API_BASE}/api/process/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(generatePayload)
      });

      if (!genResponse.ok) {
        const errorData = await genResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || `Generation failed: ${genResponse.statusText}`);
      }

      const genResult = await genResponse.json();
      const backendBasename = genResult.basename || versionedBasename;
      versionedBasename = backendBasename;
      setPdfBasename(backendBasename);

      setLogBasename(backendBasename);
      setShowLogs(true);
      setProcessingStage('Waiting for slide generation to complete...');
      await startStreamingLogs(backendBasename);

      setProcessingStage('Verifying slides were generated...');

      const slidesData = await waitForSlidesReady(versionedBasename, 6, 2500);
      if (!slidesData.slides || slidesData.slides.length === 0) {
        throw new Error('No slides were generated from the document. Please check the backend logs.');
      }

      setProcessingStage('Finalizing...');
      await updateDocumentStatus(docId, 'ready_for_processing');

      const fileType = existingDoc?.fileType ||
        (uploadedFile?.type.includes('pdf') ? 'PDF' : 'DOCX');

      const newDoc: Document = {
        id: docId,
        name: filename,
        fileType,
        status: 'ready_for_processing',
        createdDate: new Date().toISOString().split('T')[0],
        size: existingDoc?.size || `${((uploadedFile?.size || 0) / (1024 * 1024)).toFixed(1)} MB`,
        generationMode: outputMode,
        slides: [],
        basename: versionedBasename,
        output_type: genResult.output_type || (outputMode === 'video' ? 'pptx+video' : 'pptx'),
        outputs: {
          generatedAt: new Date().toLocaleString()
        }
      };

      onUpload(newDoc);
      toast.success(existingDoc ? 'Presentation re-generated successfully!' : 'Document processed successfully! Ready for editing.');

      if (pollerRef.current) {
        clearInterval(pollerRef.current);
        pollerRef.current = null;
      }

      setIsProcessing(false);
      navigateToEditPage(newDoc);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
      toast.error(errorMessage);
      setIsProcessing(false);
      setActiveStep('persona');

      if (pollerRef.current) {
        clearInterval(pollerRef.current);
        pollerRef.current = null;
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white p-6 md:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 page-hero-container text-white shadow-md mb-8">
          <h1 className="page-hero-title mb-1 flex items-center gap-2">
            {existingDoc && <RefreshCcw className="w-4 h-4 text-indigo-200" />}
            {existingDoc ? 'Regenerate Presentation' : 'Create a Presentation'}
          </h1>
          <p className="page-hero-subtitle text-indigo-100">
            {existingDoc
              ? `Reconfigure settings for "${existingDoc.name}" and regenerate your presentation`
              : 'Upload a document to automatically generate an interactive AI-powered presentation'}
          </p>
        </div>

        {/* Step Indicator */}
        <div className="flex justify-center items-center gap-0 mb-8">
          {visibleSteps.map((step, idx) => {
            const currentStepIndex = allSteps.indexOf(activeStep);
            const visibleStepIndex = allSteps.indexOf(step);
            const isCompleted = visibleStepIndex < currentStepIndex;
            const isActive = currentActiveStep === step;

            return (
              <div key={step} className="flex flex-col items-center">
                {/* Connection Line (before circle) */}
                {idx > 0 && (
                  <div
                    className="absolute h-1 transition-all"
                    style={{
                      width: '60px',
                      left: `calc(-30px - ${(idx - 1) * 120}px)`,
                      top: '24px',
                      backgroundColor: visibleStepIndex <= currentStepIndex ? '#6366F1' : '#e2e8f0'
                    }}
                  />
                )}

                {/* Circle Button */}
                <button
                  onClick={() => navigateToStep(step)}
                  disabled={!canNavigateToStep(step)}
                  className={`w-12 h-12 rounded-full flex items-center justify-center font-semibold transition-all mb-3 relative z-20 ${
                    isActive
                      ? 'bg-indigo-600 text-white scale-110'
                      : isCompleted
                      ? 'bg-indigo-600 text-white cursor-pointer hover:scale-105'
                      : 'bg-slate-200 text-slate-600 cursor-not-allowed'
                  }`}
                  title={`Go to step ${idx + 1}: ${step}`}
                >
                  {idx + 1}
                </button>

                {/* Step Label */}
                <p className="text-xs font-medium text-slate-600 capitalize text-center w-16">
                  {step === 'upload' ? 'Upload' : step === 'template' ? 'Template' : step === 'domain' ? 'Domain' : step === 'persona' ? 'Audience' : 'Processing'}
                </p>
              </div>
            );
          })}
        </div>

        {/* Upload Step */}
        {activeStep === 'upload' && (
          <Card className={designTokens.components.uploadSection.card}>
            <CardHeader>
              <CardTitle>Upload Your Document</CardTitle>
              <CardDescription>
                Upload a PDF or DOCX with your content — we’ll turn it into slides (max 10MB)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">

              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 ${
                  isDragging
                    ? 'border-indigo-500 bg-gradient-to-br from-indigo-50 to-purple-50 scale-105'
                    : 'border-slate-300 hover:border-indigo-400 hover:bg-slate-50'
                }`}
              >
                <Upload className="w-10 h-10 mx-auto mb-2 text-indigo-600" />
                <h3 className="mb-1 text-slate-900 font-semibold text-base">Drag and drop your file</h3>
                <p className="text-slate-600 mb-4 text-sm">PDF or DOCX (up to 10MB)</p>
                <label htmlFor="file-upload">
                  <Button 
                    type="button" 
                    size="sm"
                    onClick={() => document.getElementById('file-upload')?.click()} 
                    className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"
                  >
                    Browse Files
                  </Button>
                  <input
                    id="file-upload"
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx"
                    onChange={handleFileSelect}
                  />
                </label>
              </div>

              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {error}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Configure Step */}
        {activeStep === 'template' && (uploadedFile || existingDoc) && (
          <div className="space-y-6">
            <Card className={designTokens.components.uploadSection.card}>
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <CheckCircle className="w-6 h-6 text-indigo-600" />
                  {existingDoc ? 'Regenerating Project' : 'File Ready'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col gap-4 p-4 bg-indigo-50 rounded-lg border border-indigo-200 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="font-medium text-slate-900">
                      {existingDoc ? existingDoc.name : uploadedFile?.name}
                    </p>
                    <p className="text-sm text-slate-600">
                      {existingDoc
                        ? (existingDoc.size || `${existingDoc.fileType} document`)
                        : uploadedFile
                          ? `${(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB`
                          : ''}
                    </p>
                    {existingDoc && (
                      <p className="text-xs text-indigo-600 mt-1 font-medium flex items-center gap-1">
                        <RefreshCcw className="w-3.5 h-3.5 text-indigo-600" /> Reconfiguring — original file will be reused
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        if (uploadedFile) {
                          await loadExtractedContent(uploadedFile);
                        } else if (existingDoc) {
                          await loadExtractedContentFromDoc(existingDoc);
                        }
                      }}
                    >
                      <Edit2 className="w-4 h-4 text-indigo-600 mr-1" />
                      Edit Content
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleRemoveFile}
                    >
                      <X className="w-4 h-4 text-indigo-600" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {showEditPanel && (
              <Card className={`${designTokens.components.uploadSection.card} border-indigo-300 bg-indigo-50`}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0">
                  <CardTitle className="flex items-center gap-2"><Edit2 className="w-3.5 h-3.5 text-indigo-600" /> Edit Document Content</CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowEditPanel(false)}
                  >
                    <X className="w-4 h-4 text-indigo-600" />
                  </Button>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-slate-900">Document Content</h3>
                      <p className="text-xs text-slate-600 mt-0.5">
                        Edit freely — add headings, rearrange sections, modify text & images
                      </p>
                    </div>

                    <div className="flex gap-2">
                      {extractedImages.length > 0 && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs"
                          onClick={() => setShowImageLibrary(!showImageLibrary)}
                        >
                          <ImageIcon className="w-3.5 h-3.5 mr-1 text-indigo-600" />
                          Images ({extractedImages.length})
                        </Button>
                      )}

                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        onClick={() =>
                          setBlocks(bs => [...bs, { id: `b${Date.now()}`, type: 'paragraph', content: '' }])
                        }
                      >
                        <Plus className="w-3.5 h-3.5 mr-1 text-indigo-600" /> Add block
                      </Button>
                    </div>
                  </div>

                  {showImageLibrary && extractedImages.length > 0 && (
                    <div className="bg-white border border-indigo-200 rounded-lg p-4 mb-4">
                      <div className="grid grid-cols-4 gap-3">
                        {extractedImages.map(img => (
                          <div
                            key={img.id}
                            onClick={() => {
                              setBlocks(prev => [
                                ...prev,
                                {
                                  id: `b${Date.now()}`,
                                  type: 'image',
                                  content: '',
                                  imageUrl: img.url,
                                },
                              ]);
                            }}
                            className="group relative aspect-video rounded-lg overflow-hidden border-2 border-slate-200 hover:border-indigo-400 cursor-pointer"
                          >
                            <img src={img.url} className="w-full h-full object-cover" />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <input
                    type="file"
                    accept="image/*"
                    ref={imageInputRef}
                    className="hidden"
                    onChange={handleImageUpload}
                  />

                  <div className="space-y-3 bg-white rounded-lg p-3 border border-slate-200">
                    {blocks.length === 0 ? (
                      <p className="text-sm text-slate-500 text-center py-4">No content extracted. Try editing or adding blocks manually.</p>
                    ) : (
                      blocks.map(block => (
                        <div
                          key={block.id}
                          className="group relative bg-slate-50 border border-slate-200 rounded-lg p-3 hover:shadow-sm transition"
                        >
                          <div className="absolute right-2 top-2 flex gap-1 opacity-0 group-hover:opacity-100 transition">
                            <select
                              value={block.type}
                              onChange={e => changeType(block.id, e.target.value as any)}
                              className="text-xs border rounded px-1 py-0.5"
                            >
                              <option value="h1">H1</option>
                              <option value="h2">H2</option>
                              <option value="paragraph">Paragraph</option>
                              <option value="image">Image</option>
                            </select>

                            <button
                              onClick={() => removeBlock(block.id)}
                              className="p-1 rounded hover:bg-red-50 text-red-500"
                            >
                              <Trash2 className="w-3.5 h-3.5 text-indigo-600" />
                            </button>
                          </div>

                          {block.type === 'image' ? (
                            <div className="w-full">
                              {block.imageUrl ? (
                                <img
                                  src={block.imageUrl}
                                  alt="block"
                                  className="w-full max-h-40 object-contain rounded border border-slate-200"
                                  onError={(e) => {
                                    console.error("Image failed:", block.imageUrl);
                                    (e.target as HTMLImageElement).style.display = "none";
                                  }}
                                />
                              ) : (
                                <div className="border border-dashed border-slate-300 rounded p-4 text-center text-slate-400 text-xs">
                                  No image selected
                                </div>
                              )}
                            </div>
                          ) : (
                            <textarea
                              value={block.content}
                              onChange={e => updateBlock(block.id, e.target.value)}
                              className={`
                                w-full bg-transparent outline-none resize-none
                                ${block.type === 'h1'
                                  ? 'text-lg font-bold text-slate-900'
                                  : block.type === 'h2'
                                  ? 'text-base font-semibold text-slate-800'
                                  : 'text-sm text-slate-600'}
                              `}
                              placeholder={
                                block.type === 'h1'
                                  ? 'Heading...'
                                  : block.type === 'h2'
                                  ? 'Subheading...'
                                  : 'Write content...'
                              }
                              rows={block.type === 'paragraph' ? 2 : 1}
                            />
                          )}

                          <div className="mt-2 flex gap-2 opacity-0 group-hover:opacity-100 transition">
                            <button
                              onClick={() => addBlock(block.id, 'paragraph')}
                              className="text-xs text-indigo-500 hover:text-indigo-700 flex items-center gap-1"
                            >
                              <Plus className="w-3 h-3 text-indigo-600" /> P
                            </button>

                            <button
                              onClick={() => addBlock(block.id, 'h2')}
                              className="text-xs text-indigo-500 hover:text-indigo-700 flex items-center gap-1"
                            >
                              <Plus className="w-3 h-3 text-indigo-600" /> H2
                            </button>

                            <button
                              onClick={() => {
                                const id = `b${Date.now()}`;
                                addBlock(block.id, 'image', id);
                                setActiveImageBlock(id);
                                setTimeout(() => {
                                  imageInputRef.current?.click();
                                }, 50);
                              }}
                              className="text-xs text-indigo-500 hover:text-indigo-700 flex items-center gap-1"
                            >
                              <Plus className="w-3 h-3 text-indigo-600" /> Img
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="flex gap-2 pt-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setShowEditPanel(false)}
                      className="flex-1"
                    >
                      Done Editing
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            <Card className={designTokens.components.uploadSection.card}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Layers className="w-3.5 h-3.5 text-indigo-600" /> Choose Template</CardTitle>
                <CardDescription>Select a design template for your slides</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-w-lg">
                  {templates.map((template) => (
                    <button
                      key={template.name}
                      type="button"
                      onClick={() => {
                        setSelectedTemplate(template.name);
                        setActiveStep('persona');
                      }}
                      className={`rounded-xl overflow-hidden transition-all border-2 ${
                        selectedTemplate === template.name
                          ? 'border-indigo-500 ring-2 ring-indigo-200'
                          : 'border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <div className="h-24 bg-slate-100 flex items-center justify-center p-2">
                        {template.previewUrl ? (
                          <img
                            src={template.previewUrl}
                            alt={template.name}
                            className="max-h-full max-w-full object-contain"
                          />
                        ) : (
                          <div className="text-slate-500 text-center">
                            <p className="font-medium">{template.name}</p>
                            <p className="text-xs mt-2">Preview unavailable</p>
                          </div>
                        )}
                      </div>
                      <div className="p-3 bg-white">
                        <p className="text-sm font-medium text-slate-900">{template.name.replace(/\.pptx$/i, '')}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Domain Step */}
        {activeStep === 'domain' && (uploadedFile || existingDoc) && (
          <div className="space-y-6">
            <Card className={designTokens.components.uploadSection.card}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Layers className="w-3.5 h-3.5 text-indigo-600" /> Domain Context</CardTitle>
                <CardDescription>Select a domain-specific context for your presentation</CardDescription>
              </CardHeader>
              <CardContent>
                {isTraineePersona ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedDomain('None');
                        setDomainPhase('selectOutput');
                      }}
                      className="rounded-2xl border px-4 py-3 text-left text-sm font-medium transition-all border-indigo-600 bg-indigo-50 text-indigo-700 shadow-sm"
                    >
                      <div className="font-semibold">No domain required</div>
                      <p className="mt-1 text-xs text-slate-500">Trainee audiences do not require specialized domain framing.</p>
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {domainOptions.map((domain) => (
                      <button
                        key={domain}
                        type="button"
                        onClick={() => {
                          setSelectedDomain(domain);
                          setDomainPhase('selectOutput');
                        }}
                        className={`rounded-2xl border px-4 py-3 text-left text-sm font-medium transition-all ${
                          selectedDomain === domain
                            ? 'border-indigo-600 bg-indigo-50 text-indigo-700 shadow-sm'
                            : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span>{domain}</span>
                          {selectedDomain === domain && (
                            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-white text-[10px] font-bold">✓</span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {domain === 'Financial Services' && 'ROI, risk, compliance'}
                          {domain === 'Banking' && 'Transactions, controls, trust'}
                        </p>
                      </button>
                    ))}
                  </div>
                )}
                <p className="mt-3 text-xs text-slate-500">Choose a domain to tailor the presentation language, examples, and framing.</p>
              </CardContent>

            {domainPhase === 'selectOutput' && (
              <Card className={designTokens.components.uploadSection.card}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><Layers className="w-3.5 h-3.5 text-indigo-600" /> What should we generate?</CardTitle>
                  <CardDescription>Choose video narration or a PPTX-only presentation.</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {(['pptx', 'video'] as const).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => handleSelectOutputMode(mode)}
                        className={`p-3 rounded-xl text-left transition-all border ${
                          outputMode === mode
                            ? 'border-indigo-600 bg-indigo-50 text-indigo-700 shadow-md'
                            : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:bg-slate-50'
                        }`}
                      >
                        <div className="font-semibold text-slate-900 text-sm mb-1">
                          {mode === 'pptx' ? 'PPTX only' : 'Video with narration'}
                        </div>
                        <p className="text-xs text-slate-600 leading-5">
                          {mode === 'pptx'
                            ? 'Download a fully editable PowerPoint file without narration.'
                            : 'Create PPTX plus AI narration and a shareable MP4 video.'}
                        </p>
                      </button>
                    ))}
                  </div>
                  <div className="flex justify-end mt-4">
                    <Button
                      size="sm"
                      className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"
                      onClick={() => {
                        if (outputMode === 'video') setDomainPhase('selectVoice');
                        else handleUpload(selectedDomain || undefined);
                      }}
                      disabled={!outputMode}
                    >
                      Continue
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {domainPhase === 'selectVoice' && (
              <Card className={designTokens.components.uploadSection.card}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><Mic className="w-3.5 h-3.5 text-indigo-600" /> Narration Voice</CardTitle>
                  <CardDescription>Choose a voice for the video narration</CardDescription>
                </CardHeader>
                <CardContent>
                  {loadingVoices ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader className="w-4 h-4 text-indigo-600 animate-spin mr-2" />
                      <span className="text-sm text-slate-600">Loading...</span>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                      {voices.map((voice) => (
                        <button
                          key={voice.id}
                          type="button"
                          onClick={() => setSelectedVoice(voice.id)}
                          className={`p-3 text-xs rounded-xl text-left transition-all border ${
                            selectedVoice === voice.id
                              ? 'border-indigo-600 bg-indigo-50 text-indigo-700 shadow-md'
                              : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:bg-slate-50'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-1">
                            <div className="flex-1 min-w-0">
                              <div className="font-semibold text-slate-900 text-sm">{voice.name}</div>
                              <p className="text-xs text-slate-600 mt-0.5">{voice.description}</p>
                              <p className="text-[11px] text-slate-500 mt-1 flex items-center gap-1"><User className="w-3.5 h-3.5 text-indigo-600" /> {voice.gender}</p>
                            </div>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                playVoicePreview(voice.id);
                              }}
                              className="ml-1 p-1 rounded-full hover:bg-slate-200 transition-colors"
                              title="Preview voice"
                            >
                              {loadingVoicePreview === voice.id ? (
                                <Loader className="w-3.5 h-3.5 text-indigo-600 animate-spin" />
                              ) : playingVoiceId === voice.id ? (
                                <Pause className="w-3.5 h-3.5 text-indigo-600" />
                              ) : (
                                <Volume2 className="w-3.5 h-3.5 text-indigo-600" />
                              )}
                            </button>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="flex justify-end mt-4">
                    <Button
                      size="sm"
                      className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"
                      onClick={() => handleUpload(selectedDomain || undefined)}
                      disabled={!selectedVoice}
                    >
                      Create Video
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
            </Card>

          </div>
        )}

        {/* Persona Step */}
        {activeStep === 'persona' && (uploadedFile || existingDoc) && (
          <div className="space-y-6">
            <Card className={designTokens.components.uploadSection.card}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Users className="w-3.5 h-3.5 text-indigo-600" /> Target Audience</CardTitle>
                <CardDescription>Select the audience for your presentation</CardDescription>
              </CardHeader>
              <CardContent>
                {personaPhase === 'selectPersona' && (
                  loadingPersonas ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader className="w-4 h-4 text-indigo-600 animate-spin mr-2" />
                      <span className="text-sm text-slate-600">Loading...</span>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {personas.map((persona) => (
                        <button
                          key={persona.id}
                          type="button"
                          onClick={() => handleSelectPersona(persona.id)}
                          className={`p-3 text-xs rounded-xl text-left transition-all border ${
                            selectedPersona === persona.id
                              ? 'border-indigo-600 bg-indigo-50 text-indigo-700 shadow-md'
                              : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:bg-slate-50'
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            <Target className="w-4 h-4 text-indigo-600 mt-0.5 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <div className="font-semibold text-slate-900 text-sm">{persona.name}</div>
                              <p className="text-xs text-slate-600 mt-0.5">{persona.description}</p>
                              <p className="text-xs text-slate-500 mt-1">
                                {persona.min_slides}-{persona.max_slides} slides recommended
                              </p>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )
                )}

                {personaPhase === 'selectSlides' && selectedPersonaObj && (
                  <div className="space-y-4">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-sm text-slate-600">Audience: <span className="font-semibold text-slate-900">{selectedPersonaObj.name}</span></p>
                      <p className="text-xs text-slate-500 mt-1">Pick a slide length that matches the audience and message strength.</p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-6 shadow-sm">
                      <p className="text-xs uppercase tracking-widest font-semibold text-slate-500 mb-6">Presentation length</p>
                      
                      <div className="flex items-end justify-between mb-6">
                        <div>
                          <p className="text-6xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">{selectedSlideCount}</p>
                          <p className="text-sm text-slate-600 mt-2">slides</p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs text-slate-500">Recommended range</p>
                          <p className="text-lg font-semibold text-slate-700">{selectedPersonaObj.min_slides}–{selectedPersonaObj.max_slides}</p>
                        </div>
                      </div>
                      
                      <div className="space-y-4">
                        <input
                          type="range"
                          min={selectedPersonaObj.min_slides}
                          max={selectedPersonaObj.max_slides}
                          value={selectedSlideCount}
                          onChange={(e) => handleSelectSlideCount(parseInt(e.target.value))}
                          onMouseUp={handleSlideCountDone}
                          onTouchEnd={handleSlideCountDone}
                          className="w-full h-3 bg-gradient-to-r from-slate-200 to-slate-300 rounded-full appearance-none cursor-pointer slider"
                          style={{
                            background: `linear-gradient(to right, rgb(229, 231, 235) 0%, rgb(229, 231, 235) ${((selectedSlideCount - selectedPersonaObj.min_slides) / (selectedPersonaObj.max_slides - selectedPersonaObj.min_slides)) * 100}%, rgb(226, 232, 240) ${((selectedSlideCount - selectedPersonaObj.min_slides) / (selectedPersonaObj.max_slides - selectedPersonaObj.min_slides)) * 100}%, rgb(226, 232, 240) 100%)`
                          }}
                        />
                        <style>{`
                          .slider::-webkit-slider-thumb {
                            appearance: none;
                            width: 24px;
                            height: 24px;
                            border-radius: 50%;
                            background: linear-gradient(135deg, rgb(79, 70, 229), rgb(147, 51, 234));
                            cursor: pointer;
                            box-shadow: 0 2px 8px rgba(79, 70, 229, 0.4);
                            border: 3px solid white;
                          }
                          .slider::-moz-range-thumb {
                            width: 24px;
                            height: 24px;
                            border-radius: 50%;
                            background: linear-gradient(135deg, rgb(79, 70, 229), rgb(147, 51, 234));
                            cursor: pointer;
                            box-shadow: 0 2px 8px rgba(79, 70, 229, 0.4);
                            border: 3px solid white;
                          }
                        `}</style>
                        
                        <div className="flex items-center justify-between text-xs text-slate-500 px-1">
                          <span className="font-medium">{selectedPersonaObj.min_slides}</span>
                          <span className="text-slate-400">•</span>
                          <span className="font-medium">{selectedPersonaObj.max_slides}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Output selection moved to Domain step */}

                {personaPhase === 'selectVoice' && (
                  <div className="space-y-4">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-sm text-slate-600">Choose narration voice</p>
                      <p className="text-xs text-slate-500 mt-1">Pick a voice for your video narration.</p>
                    </div>
                    {loadingVoices ? (
                      <div className="flex items-center justify-center py-4">
                        <Loader className="w-4 h-4 text-indigo-600 animate-spin mr-2" />
                        <span className="text-sm text-slate-600">Loading...</span>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                        {voices.map((voice) => (
                          <button
                            key={voice.id}
                            type="button"
                            onClick={() => handleSelectVoice(voice.id)}
                            className={`p-3 text-xs rounded-xl text-left transition-all border ${
                              selectedVoice === voice.id
                                ? 'border-indigo-600 bg-indigo-50 text-indigo-700 shadow-md'
                                : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:bg-slate-50'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-1">
                              <div className="flex-1 min-w-0">
                                <div className="font-semibold text-slate-900 text-sm">{voice.name}</div>
                                <p className="text-xs text-slate-600 mt-0.5">{voice.description}</p>
                                <p className="text-[11px] text-slate-500 mt-1 flex items-center gap-1"><User className="w-3.5 h-3.5 text-indigo-600" /> {voice.gender}</p>
                              </div>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  playVoicePreview(voice.id);
                                }}
                                className="ml-1 p-1 rounded-full hover:bg-slate-200 transition-colors"
                                title="Preview voice"
                              >
                                {loadingVoicePreview === voice.id ? (
                                  <Loader className="w-3.5 h-3.5 text-indigo-600 animate-spin" />
                                ) : playingVoiceId === voice.id ? (
                                  <Pause className="w-3.5 h-3.5 text-indigo-600" />
                                ) : (
                                  <Volume2 className="w-3.5 h-3.5 text-indigo-600" />
                                )}
                              </button>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="flex justify-end">
                      <Button
                        size="sm"
                        className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"
                        onClick={handlePersonaContinue}
                        disabled={!selectedVoice}
                      >
                        Continue
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Processing Step */}
        {activeStep === 'processing' && (
          <Card className={designTokens.components.uploadSection.card}>
            <CardHeader>
              <CardTitle className="flex items-center gap-3">
                <Loader className="w-6 h-6 text-indigo-600 animate-spin" />
                Processing Your Document
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">

              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-700">{processingStage}</p>
                <div className="w-full bg-slate-200 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-indigo-600 to-purple-600 h-2 rounded-full"
                    style={{
                      width: processingStage === 'Uploading file...' ? '25%' :
                        processingStage === 'Uploading and generating slides...' ? '50%' :
                        processingStage === 'Waiting for slide generation to complete...' ? '75%' : '95%'
                    }}
                  />
                </div>
              </div>

              {/* Live Logs - Collapsible */}
              <div className="border border-slate-300 rounded-lg bg-slate-900 p-4 font-mono text-xs">
                <button
                  onClick={() => setShowLogs(!showLogs)}
                  className="w-full flex items-center justify-between mb-3 hover:opacity-80 transition-opacity"
                >
                  <div>
                    <h4 className="text-slate-300 font-semibold flex items-center gap-2">
                      <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                      Processing Logs
                    </h4>
                    {logBasename && (
                      <p className="text-slate-500 text-xs mt-1">
                        Streaming from <span className="font-medium text-slate-300">logs/{logBasename}.log</span>
                      </p>
                    )}
                  </div>
                  <span className="text-slate-500 text-xs flex items-center gap-2">
                    {logs.length} entries
                    <ChevronDown
                      className={`w-4 h-4 transition-transform ${showLogs ? 'rotate-180' : ''}`}
                    />
                  </span>
                </button>

                {/* Logs Content - Hidden by default */}
                {showLogs && (
                  <div className="max-h-96 overflow-y-auto bg-slate-950 rounded p-3 space-y-1">
                    {logs.length === 0 ? (
                      <div className="text-slate-600">Waiting for updates...</div>
                    ) : (
                      logs.map((log, idx) => {
                        let textColor = 'text-slate-300';
                        if (log.includes('[ERROR]') || log.toLowerCase().includes('error')) {
                          textColor = 'text-red-400';
                        } else if (log.includes('✓') || log.toLowerCase().includes('success')) {
                          textColor = 'text-green-400';
                        } else if (log.includes('WARNING')) {
                          textColor = 'text-yellow-400';
                        } else if (log.includes('INFO') || log.includes('==')) {
                          textColor = 'text-blue-400';
                        }
                        return (
                          <div key={idx} className={`${textColor} whitespace-pre-wrap break-words`}>
                            {log}
                          </div>
                        );
                      })
                    )}
                    <div ref={logsEndRef} />
                  </div>
                )}
              </div>

              <p className="text-sm text-slate-600 flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-500" />
                This may take a few minutes depending on your document size...
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}