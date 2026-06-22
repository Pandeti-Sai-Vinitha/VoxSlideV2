import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, FileText, Eye, Trash2, RefreshCw,
  LayoutGrid, List, Layers, Clock, CheckCircle2,
  AlertCircle, Loader2, Play, Wand2, Info
} from 'lucide-react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';

interface Document {
  id: number | string;
  name: string;
  fileType: string;
  status: string;
  size?: string;
  createdDate: string;
  basename?: string;
  output_type?: string;
}

// ─── Status helpers ───────────────────────────────────────────────────────────

const STATUS_META: Record<string, {
  label: string;
  color: string;
  badgeCls: string;
  icon: React.ReactNode;
}> = {
  new:                  { label: 'New',                color: 'indigo',   badgeCls: 'bg-indigo-100 text-indigo-700 border-indigo-300',   icon: <Layers className="w-3.5 h-3.5" /> },
  Uploading:            { label: 'Uploading',           color: 'orange',   badgeCls: 'bg-orange-100 text-orange-700 border-orange-300',   icon: <Loader2 className="w-3.5 h-3.5 animate-spin" /> },
  uploading:            { label: 'Uploading',           color: 'orange',   badgeCls: 'bg-orange-100 text-orange-700 border-orange-300',   icon: <Loader2 className="w-3.5 h-3.5 animate-spin" /> },
  processing:           { label: 'Processing',          color: 'blue',     badgeCls: 'bg-blue-100 text-blue-700 border-blue-300',         icon: <Loader2 className="w-3.5 h-3.5 animate-spin" /> },
  ready_for_processing: { label: 'Ready for Processing', color: 'pink',     badgeCls: 'bg-pink-100 text-pink-700 border-pink-300',         icon: <Play className="w-3.5 h-3.5" /> },
  completed:            { label: 'Completed',           color: 'emerald',  badgeCls: 'bg-emerald-100 text-emerald-700 border-emerald-300',icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
  failed:               { label: 'Failed',              color: 'red',      badgeCls: 'bg-red-100 text-red-700 border-red-300',            icon: <AlertCircle className="w-3.5 h-3.5" /> },
};

const getMeta = (s: string) =>
  STATUS_META[s] ?? { label: s, color: 'slate', badgeCls: 'bg-slate-100 text-slate-700 border-slate-300', icon: <Layers className="w-3.5 h-3.5" /> };

// ─── Gradient palettes per file type ─────────────────────────────────────────
const FILE_GRADIENTS: Record<string, string> = {
  pdf:  'from-rose-500 to-pink-600',
  docx: 'from-sky-500 to-indigo-600',
  doc:  'from-sky-500 to-indigo-600',
  html: 'from-amber-500 to-orange-600',
};
const getGradient = (ft = '') => FILE_GRADIENTS[ft.toLowerCase()] ?? 'from-violet-500 to-purple-700';

// ─────────────────────────────────────────────────────────────────────────────

interface LibraryPageProps {
  documents?: Document[];
}

export default function LibraryPage({ documents: propDocuments = [] }: LibraryPageProps) {
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<'all' | 'projects'>('all');
  const [documents, setDocuments] = useState<Document[]>([]);
  // ✅ LOAD FROM CACHE (runs once)
  useEffect(() => {
    const cached = sessionStorage.getItem('library_docs');
    if (cached) {
      try {
        setDocuments(JSON.parse(cached));
      } catch {}
    }
  }, []);
  const [isFetching, setIsFetching] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<string | null>(null);

  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [statusDialogTitle, setStatusDialogTitle] = useState('');
  const [statusDialogMessage, setStatusDialogMessage] = useState('');

  const [expandedProjectId, setExpandedProjectId] = useState<string | null>(null);
  const [selectedVersionByGroup, setSelectedVersionByGroup] = useState<Record<string, number>>({});
  const [infoVersion, setInfoVersion] = useState<GroupedProject['versions'][0] | null>(null);
  const [infoDialogOpen, setInfoDialogOpen] = useState(false);

  const resolveApiBase = () => {
    const raw = (import.meta as any).env?.VITE_API_BASE_URL || (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
    if (typeof raw !== 'string' || !raw.trim()) return 'http://localhost:8000';
    if (raw.startsWith(':')) return `http://localhost${raw}`;
    if (raw.startsWith('//')) return `http:${raw}`;
    return raw.replace(/\/$/, '');
  };

  // ── Fetch ──────────────────────────────────────────────────────────────────
  const fetchDocuments = async () => {
    const API_BASE = resolveApiBase();

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    try {
      const res = await fetch(
        `${API_BASE}/api/documents?page=1&limit=1000`,
        { signal: controller.signal }
      );

      clearTimeout(timeout);

      if (!res.ok) {
        throw new Error(`Failed to fetch documents: ${res.status}`);
      }

      const text = await res.text();

      try {
        return JSON.parse(text);
      } catch {
        throw new Error('Invalid JSON response from server');
      }

    } catch (err) {
      console.warn("⚠️ Fetch failed or timed out. Keeping existing data.");
      return { items: [] };  // ✅ VERY IMPORTANT
    }
  };

  const normalizeDocumentId = (id: string | number | undefined): string => id === undefined || id === null ? '' : String(id);

  const mergeDocuments = (backendDocs: Document[], localDocs: Document[]): Document[] => {
    const lookup = new Map<string, Document>();
    backendDocs.forEach(doc => lookup.set(normalizeDocumentId(doc.id), doc));
    localDocs.forEach(doc => {
      const key = normalizeDocumentId(doc.id);
      if (!lookup.has(key)) lookup.set(key, doc);
    });
    return Array.from(lookup.values());
  };

  useEffect(() => {
    // Apply prop updates to any documents that exist in current state
    // This allows status changes (e.g., uploading → processing) to propagate immediately
    setDocuments(prev => {
      return prev.map(doc => {
        const propsVersion = propDocuments.find(
          p => normalizeDocumentId(p.id) === normalizeDocumentId(doc.id)
        );
        return propsVersion ? { ...doc, ...propsVersion } : doc;
      });
    });
  }, [propDocuments]);

  useEffect(() => {
    let isMounted = true;
    let intervalId: number | null = null;
    let isFirstLoad = true;

    const loadDocuments = async () => {
      if (!isMounted) return;
      setError(null);
      if (isFirstLoad && documents.length === 0) {
        setIsFetching(true);
      }

      try {
        const docsRes = await fetchDocuments();
        if (!isMounted) return;
        const backendDocs = docsRes.items || [];
        setDocuments(prev => {
          if (backendDocs.length === 0 && prev.length > 0) {
            return prev;
          }

          const merged = mergeDocuments(backendDocs, prev);

          // ✅ SAVE TO CACHE
          sessionStorage.setItem('library_docs', JSON.stringify(merged));

          return merged;
        });

      } catch (e: any) {
        if (!isMounted) return;
        setError(e.message || 'Failed to load documents');
      } finally {
        if (isMounted) {
          setIsFetching(false);
          isFirstLoad = false;
        }
      }
    };

    loadDocuments().catch(() => {});
    intervalId = window.setInterval(() => loadDocuments().catch(() => {}), 25000);

    return () => {
      isMounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  // ── Grouped projects structure ────────────────────────────────────────────
  interface GroupedProject {
    id: string;
    name: string;
    fileType: string;
    size?: string;
    versions: Array<{
      version: number;
      basename: string;
      document_id: string;
      template?: string;
      persona?: string;
      voice?: string;      output_type?: string;      slides_count?: number;
      status: string;
      createdDate: string;
      doc: Document;
    }>;
  }

  const [versionDetailsMap, setVersionDetailsMap] = useState<Record<string, any>>({});

  // Fetch version details from backend
  const fetchVersionDetails = async (baseName: string, docId: string) => {
    if (versionDetailsMap[baseName]) return; // Already fetched
    
    try {
      const API_BASE = resolveApiBase();
      const res = await fetch(`${API_BASE}/api/documents/${docId}/versions`);
      if (res.ok) {
        const data = await res.json();
        setVersionDetailsMap(prev => ({
          ...prev,
          [baseName]: data.versions || []
        }));
      }
    } catch (e) {
      console.error(`Failed to fetch versions for ${baseName}:`, e);
    }
  };

  const groupedProjects = (() => {
    const groups: Record<string, GroupedProject> = {};

    documents.forEach(doc => {
      // Extract base_name by removing "_vX" suffix from basename (Requirement 1)
      const fullName = doc.basename || doc.name;
      const nameWithoutVersion = fullName.replace(/_v\d+$/, '');
      
      // Try to extract version number
      const versionMatch = fullName.match(/_v(\d+)$/);
      const versionNum = versionMatch ? parseInt(versionMatch[1], 10) : 1;

      const actualBaseName = nameWithoutVersion;

      // Initialize group if not exists (Requirement 2: use actualBaseName)
      if (!groups[actualBaseName]) {
        groups[actualBaseName] = {
          id: actualBaseName,
          name: actualBaseName,
          fileType: doc.fileType,
          size: doc.size,
          versions: [],
        };
      }

      // Add full version info (Requirement 3: include metadata)
      groups[actualBaseName].versions.push({
        version: versionNum,
        basename: doc.basename || doc.name,
        document_id: String(doc.id),
        template: (doc as any).template,
        persona: (doc as any).persona,
        voice: (doc as any).voice,
        output_type: (doc as any).output_type,
        slides_count: (doc as any).slides_count,
        status: doc.status,
        createdDate: doc.createdDate,
        doc,
      });

      // Fetch version details from backend
            
      if (doc.id && doc.status !== 'deleted') {
        fetchVersionDetails(actualBaseName, String(doc.id));
      }

    });

    // Sort versions ascending by version number for each group (Requirement 4)
    Object.values(groups).forEach(group => {
      group.versions.sort((a, b) => a.version - b.version);
    });

    // Merge backend version details into grouped projects.
    // Attach the real `doc` object from `documents` when backend returns a `document_id`.
    Object.values(groups).forEach(group => {
      const backendVersions = versionDetailsMap[group.id];
      if (backendVersions && Array.isArray(backendVersions)) {
        group.versions = backendVersions.map((backendVer: any) => {
          const existingVer = group.versions.find(v => v.version === backendVer.version);
          // Prefer an existing attached doc, otherwise find it in the flat `documents` list by id
          let attachedDoc: Document | undefined = undefined as any;
          if (existingVer?.doc && (existingVer.doc as any).id) attachedDoc = existingVer.doc;
          if (!attachedDoc && backendVer.document_id) {
            attachedDoc = documents.find(d => String(d.id) === String(backendVer.document_id));
            // If still not found, create a minimal stub so navigation and reconfigure have an id and basic fields
            if (!attachedDoc) {
              attachedDoc = {
                id: backendVer.document_id || backendVer.basename,
                name: group.name,
                fileType: group.fileType,
                status: backendVer.status || 'new',
                size: group.size,
                createdDate: backendVer.created_date || '',
                basename: backendVer.basename,
                output_type: backendVer.output_type,
              } as Document;
            }
          }
          if (!attachedDoc) attachedDoc = ({} as Document);

          return {
            version: backendVer.version,
            basename: backendVer.basename,
            document_id: backendVer.document_id,
            template: backendVer.template,
            persona: backendVer.persona,
            voice: backendVer.voice,
            output_type: backendVer.output_type,
            slides_count: backendVer.slides_count,
            status: backendVer.status,
            createdDate: backendVer.created_date,
            doc: attachedDoc,
          };
        });
      }
    });

    return groups;
  })();

  // ── Filtered views ─────────────────────────────────────────────────────────
  const filteredAll = documents.filter(doc => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || doc.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Projects = documents that have been at least partially processed
  const projects = documents.filter(doc => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    const isProject = ['completed', 'ready_for_processing', 'processing', 'failed'].includes(doc.status);
    return matchesSearch && isProject;
  });

  // Filtered grouped projects
  const filteredGroupedProjects = Object.values(groupedProjects).filter(group => {
    const matchesSearch = group.name.toLowerCase().includes(searchQuery.toLowerCase());
    const hasMatchingVersion = group.versions.some(v => {
      const isProject = ['completed', 'ready_for_processing', 'processing', 'failed'].includes(v.status);
      return isProject;
    });
    return matchesSearch && hasMatchingVersion;
  });

  // ── Actions ────────────────────────────────────────────────────────────────
  const handleDeleteClick = (id: string | number) => {
    setDocumentToDelete(String(id));
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!documentToDelete) {
      setDeleteDialogOpen(false);
      return;
    }

    setIsDeleting(true);
    setError(null);

    try {
      const API_BASE = resolveApiBase();

      const res = await fetch(`${API_BASE}/delete/${documentToDelete}`, {
        method: 'DELETE',
      });

      if (!res.ok && res.status !== 204) {
        const errText = await res.text();
        throw new Error(errText || `Failed to delete: ${res.status}`);
      }

      // ✅ REMOVE FROM UI + CACHE
      setDocuments(prev => {
        const updated = prev.filter(d => String(d.id) !== documentToDelete);

        sessionStorage.setItem('library_docs', JSON.stringify(updated));

        return updated;
      });

    } catch (e: any) {
      setError(e.message || 'Failed to delete document');
    } finally {
      setDeleteDialogOpen(false);
      setDocumentToDelete(null);
      setIsDeleting(false);
    }
  };

  const handleView = (doc: Document) => {
    const s = doc.status.toLowerCase().replace(/\s+/g, '_');

    if (s === 'uploading') {
      setStatusDialogTitle('Still uploading');
      setStatusDialogMessage('This document is still being uploaded. Please wait.');
      setStatusDialogOpen(true);
      return;
    }

    if (s === 'new') {
      setStatusDialogTitle('Not processed yet');
      setStatusDialogMessage('This document has not been processed yet.');
      setStatusDialogOpen(true);
      return;
    }

    if (s === 'processing') {
      setStatusDialogTitle('Processing');
      setStatusDialogMessage('Please wait until processing completes.');
      setStatusDialogOpen(true);
      return;
    }

    // If status is ready_for_processing, go to Edit page
    if (s === 'ready_for_processing') {
      navigate(`/edit/${String(doc.id)}`, { state: { document: doc } });
      return;
    }

    // If status is completed, go to Results page
    if (s === 'completed') {
      navigate(`/results/${String((doc as any).id || (doc as any).basename)}`, { state: { document: doc } });
      return;
    }

    // Otherwise, default to Edit page
    navigate(`/edit/${String(doc.id)}`, { state: { document: doc } });
  };

  // Navigate to Upload page pre-loaded with this project for regeneration
  const handleRegenerate = (doc: Document) => {
    navigate('/upload', { state: { editDocument: doc } });
  };

  const getStatusBadge = (status: string) => {
    const { label, badgeCls, icon } = getMeta(status);
    return (
      <Badge variant="outline" className={`${badgeCls} flex items-center gap-1`}>
        {icon} {label}
      </Badge>
    );
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* ── Hero Banner ── */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 page-hero-container text-white shadow-md">
          <h1 className="page-hero-title">Document Library</h1>
          <p className="page-hero-subtitle text-indigo-100">Manage all your documents and regenerate presentations with updated settings.</p>
        </div>

        {/* ── Tab Switcher ── */}
        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl w-fit">
          <button
            onClick={() => setActiveTab('all')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
              activeTab === 'all'
                ? 'bg-white text-indigo-700 shadow-md shadow-indigo-100'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <List className="w-4 h-4" />
            All Documents
            <span className={`ml-1 text-xs px-2 py-0.5 rounded-full font-semibold ${
              activeTab === 'all' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-200 text-slate-600'
            }`}>{documents.length}</span>
          </button>
          <button
            onClick={() => setActiveTab('projects')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
              activeTab === 'projects'
                ? 'bg-white text-indigo-700 shadow-md shadow-indigo-100'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <LayoutGrid className="w-4 h-4" />
            Projects
            <span className={`ml-1 text-xs px-2 py-0.5 rounded-full font-semibold ${
              activeTab === 'projects' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-200 text-slate-600'
            }`}>{projects.length}</span>
          </button>
        </div>

        {/* ── Search / Filter bar (shared) ── */}
        <Card className="border-indigo-100 shadow-lg bg-white/80 backdrop-blur-sm">
          <CardContent className="p-6">
            <div className="flex gap-4 mb-6">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  placeholder="Search documents..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
              {activeTab === 'all' && (
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="new">New</SelectItem>
                    <SelectItem value="Uploading">Uploading</SelectItem>
                    <SelectItem value="ready_for_processing">Ready for Processing</SelectItem>
                    <SelectItem value="processing">Processing</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* ══════════════════ ALL DOCUMENTS TAB ══════════════════ */}
            {activeTab === 'all' && (
              <div className="overflow-x-auto">
                
                {error ? (
                  <div className="text-center py-10 text-red-500">{error}</div>
                ) : documents.length === 0 ? null :
                (
                  <table className="w-full">
                    <thead className="bg-slate-50 border-b border-slate-200">
                      <tr>
                        {['Document Name', 'File Type', 'Output', 'Status', 'Created Date', 'Actions'].map(h => (
                          <th key={h} className="px-2 py-2 text-left text-xs text-slate-600 uppercase tracking-wider">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {filteredAll.map(doc => {
                        // Requirement 6: Show version in table
                        const fullName = doc.basename || doc.name;
                        const versionMatch = fullName.match(/(.+)_v(\d+)$/);
                        const base = versionMatch ? versionMatch[1] : fullName;
                        const version = versionMatch ? versionMatch[2] : '1';
                        const versionGroup = groupedProjects[base];
                        const selectedIndex = versionGroup
                          ? selectedVersionByGroup[versionGroup.id] ?? versionGroup.versions.findIndex(v => v.basename === fullName) ?? 0
                          : 0;
                        const selectedVersion = versionGroup
                          ? versionGroup.versions[selectedIndex]
                          : {
                              version: Number(version),
                              basename: fullName,
                              template: (doc as any).template,
                              persona: (doc as any).persona,
                              voice: (doc as any).voice,
                              slides: (doc as any).slides,
                              status: doc.status,
                              createdDate: doc.createdDate,
                              doc,
                            } as any;

                        return (
                        <tr key={doc.id} className="hover:bg-slate-50 transition-colors">
                          <td className="px-2 py-2">
                            <div className="flex items-center gap-2">
                              <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${getGradient(doc.fileType)} flex items-center justify-center flex-shrink-0`}>
                                <FileText className="w-3.5 h-3.5 text-white" />
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <div className="text-slate-900 font-medium text-sm">{base}</div>

                                  <Button
    variant="ghost"
    size="sm"
    className="p-0 text-slate-400 hover:text-indigo-600"
    onClick={() => {
      setInfoVersion(selectedVersion);
      setInfoDialogOpen(true);
    }}
    title="View version details"
  >
    <Info className="w-4 h-4" />
  </Button>
</div>
                              </div>
                            </div>
                          </td>
                          <td className="px-2 py-2 text-xs text-slate-700">{doc.fileType?.toUpperCase()}</td>
                          <td className="px-2 py-2 text-xs text-slate-700">
                            {doc.output_type === 'pptx+video' ? 'PPTX + Video' : 'PPTX'}
                          </td>
                          <td className="px-2 py-2">{getStatusBadge(doc.status)}</td>
                          <td className="px-2 py-2 text-xs text-slate-600">
                            <div className="flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5 text-slate-400" />
                              {doc.createdDate ? new Date(doc.createdDate).toLocaleDateString() : '—'}
                            </div>
                          </td>
                          <td className="px-2 py-2">
                            <div className="flex flex-wrap gap-1.5">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleView(doc)}
                                title="View Results"
                              >
                                <Eye className="w-4 h-4" />
                              </Button>

                              {['completed', 'ready_for_processing', 'failed'].includes(doc.status) && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => navigate(`/edit/${String(doc.id)}`, { state: { document: doc } })}
                                  title="Reprocess"
                                  className="text-indigo-500 hover:text-indigo-700 hover:bg-indigo-50"
                                >
                                  <RefreshCw className="w-4 h-4" />
                                </Button>
                              )}
                              <Button variant="ghost" size="sm" onClick={() => handleDeleteClick(doc.id)} title="Delete">
                                <Trash2 className="w-4 h-4 text-red-500" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}

                {!isFetching && !error && filteredAll.length === 0 && (
                  <div className="text-center py-16">
                    <FileText className="w-12 h-12 mx-auto text-slate-300 mb-4" />
                    <h3 className="text-slate-900 font-semibold mb-2">No documents found</h3>
                    <p className="text-slate-500 text-sm mb-4">
                      {searchQuery || statusFilter !== 'all' ? 'Try adjusting your search or filters' : 'Upload your first document to get started'}
                    </p>
                    <Button
                      onClick={() => navigate('/upload')}
                      className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-md"
                    >
                      Upload Document
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* ══════════════════ PROJECTS TAB ══════════════════ */}
            {activeTab === 'projects' && (
              <>
                {isFetching && filteredGroupedProjects.length === 0 ? (
                  <div className="flex items-center justify-center py-16 gap-3 text-slate-500">
                    <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
                    Loading projects…
                  </div>
                ) : error ? (
                  <div className="text-center py-10 text-red-500">{error}</div>
                ) : filteredGroupedProjects.length === 0 ? (
                  <div className="text-center py-16">
                    <LayoutGrid className="w-12 h-12 mx-auto text-slate-300 mb-4" />
                    <h3 className="text-slate-900 font-semibold mb-2">No projects yet</h3>
                    <p className="text-slate-500 text-sm mb-4">
                      {searchQuery ? 'No projects match your search' : 'Upload and process a document to create your first project'}
                    </p>
                    <Button
                      onClick={() => navigate('/upload')}
                      className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-md"
                    >
                      Create Project
                    </Button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
  {filteredGroupedProjects.map(group => {
    const latestVersion = group.versions.reduce(
      (max, curr) => (curr.version > max.version ? curr : max),
      group.versions[0]
    );

    const selectedVersionIndex =
      selectedVersionByGroup[group.id] ??
      group.versions.findIndex(v => v.version === latestVersion.version) ??
      0;

    const selectedVersion = group.versions[selectedVersionIndex];
    const { label, badgeCls, icon } = getMeta(selectedVersion.status);

    return (
      <div
        key={group.id}
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-md transition flex flex-col h-full"
      >
        {/* HEADER */}
        <div className="flex justify-between items-start gap-2">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center">
              <FileText className="w-4 h-4 text-slate-600" />
            </div>

            <div className="min-w-0">
              <p className="font-semibold text-slate-900 text-sm truncate">
                {group.name}
              </p>
              <p className="text-xs text-slate-400">
                {group.fileType?.toUpperCase()} • {group.size || '—'}
              </p>
            </div>
          </div>

          <Badge className={`${badgeCls} text-xs flex gap-1`}>
            {icon} {label}
          </Badge>
        </div>

        {/* VERSION SELECT */}
        <div className="mt-4">
          <Select
            value={String(selectedVersionIndex)}
            onValueChange={(value) =>
              setSelectedVersionByGroup(prev => ({
                ...prev,
                [group.id]: Number(value),
              }))
            }
          >
            <SelectTrigger className="w-full text-xs h-8">
              <SelectValue placeholder={`v${selectedVersion.version}`} />
            </SelectTrigger>
            <SelectContent>
              {group.versions.map((ver, idx) => (
                <SelectItem key={ver.basename} value={String(idx)}>
                  v{ver.version} · {getMeta(ver.status).label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* DETAILS */}
        <div className="mt-3 text-xs text-slate-600 space-y-1">
          {selectedVersion.template && (
            <div>Template: {selectedVersion.template}</div>
          )}
          {selectedVersion.persona && (
            <div>Persona: {selectedVersion.persona}</div>
          )}
          {selectedVersion.voice && (
            <div>Voice: {selectedVersion.voice}</div>
          )}
          {selectedVersion.slides_count !== undefined && (
            <div>Slides: {selectedVersion.slides_count}</div>
          )}
        </div>

        {/* DATE */}
        <div className="flex items-center gap-1 text-xs text-slate-400 mt-3">
          <Clock className="w-3 h-3" />
          {selectedVersion.createdDate
            ? new Date(selectedVersion.createdDate).toLocaleDateString(
                'en-US',
                { year: 'numeric', month: 'short', day: 'numeric' }
              )
            : '—'}
        </div>

        {/* FOOTER */}
        <div className="mt-auto pt-4 border-t border-slate-100 flex gap-2">
          {selectedVersion.status === 'completed' && (
            <Button
              size="sm"
              variant="outline"
              className="flex-1 text-xs"
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/results/${String(
                  selectedVersion.document_id ||
                  selectedVersion.doc?.id ||
                  selectedVersion.basename
                )}`);
              }}
            >
              <Eye className="w-3 h-3 mr-1" />
              View
            </Button>
          )}

          {['completed', 'ready_for_processing', 'failed'].includes(selectedVersion.status) && (
            <Button
              size="sm"
              className="flex-1 text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
              onClick={(e) => {
                e.stopPropagation();
                navigate('/upload', {
                  state: {
                    editDocument: selectedVersion.doc,
                    versionConfig: selectedVersion,
                  },
                });
              }}
            >
              <Wand2 className="w-3 h-3 mr-1" />
              Regenerate
            </Button>
          )}

          <Button
            size="sm"
            variant="ghost"
            className="text-red-500 hover:bg-red-50"
            onClick={(e) => {
              e.stopPropagation();
              handleDeleteClick(selectedVersion.doc.id);
            }}
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>
    );
  })}
</div>

                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Delete dialog ── */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Document</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this document? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-red-600 hover:bg-red-700">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ── Status info dialog ── */}
      <Dialog open={statusDialogOpen} onOpenChange={setStatusDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{statusDialogTitle}</DialogTitle>
          </DialogHeader>
          <DialogDescription>{statusDialogMessage}</DialogDescription>
          <div className="flex justify-end mt-4">
            <Button onClick={() => setStatusDialogOpen(false)} autoFocus>OK</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Version info dialog ── */}
      <Dialog open={infoDialogOpen} onOpenChange={setInfoDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Version Details</DialogTitle>
          </DialogHeader>
          {infoVersion ? (
            <div className="space-y-3 text-sm text-slate-700">
              <div><span className="font-semibold">Basename:</span> {infoVersion.basename}</div>
              <div><span className="font-semibold">Version:</span> v{infoVersion.version}</div>
              {infoVersion.template && <div><span className="font-semibold">Template:</span> {infoVersion.template}</div>}
              {infoVersion.persona && <div><span className="font-semibold">Persona:</span> {infoVersion.persona}</div>}
              {infoVersion.voice && <div><span className="font-semibold">Voice:</span> {infoVersion.voice}</div>}
              {infoVersion.output_type && <div><span className="font-semibold">Output:</span> {infoVersion.output_type === 'pptx+video' ? 'PPTX + Video' : 'PPTX'}</div>}
              {infoVersion.slides_count !== undefined && <div><span className="font-semibold">Slides:</span> {infoVersion.slides_count}</div>}
              <div><span className="font-semibold">Status:</span> {getMeta(infoVersion.status).label}</div>
              {infoVersion.createdDate && <div><span className="font-semibold">Created:</span> {new Date(infoVersion.createdDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}</div>}
            </div>
          ) : (
            <div className="text-sm text-slate-500">No version details available.</div>
          )}
          <div className="flex justify-end mt-4">
            <Button onClick={() => setInfoDialogOpen(false)} autoFocus>Close</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}