import { useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { FileText, Clock, CheckCircle, Upload, ArrowRight, Loader, Play, Layers, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';

interface Document {
  id: number | string;
  name: string;
  fileType: string;
  status: string;
  size: string;
  createdDate: string;
  updatedDate?: string;
  allowedActions?: string[];
}

interface Stats {
  total: number;
  processing: number;
  completed: number;
}

interface DashboardPageProps {
  documents?: Document[];
}

const computeStats = (docs: Document[]): Stats => ({
  total: docs.length,
  processing: docs.filter(doc => doc.status === 'processing').length,
  completed: docs.filter(doc => doc.status === 'completed').length,
});

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

export default function DashboardPage({ documents: propDocuments = [] }: DashboardPageProps) {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const docsPerPage = 5;

  useEffect(() => {
  const cached = sessionStorage.getItem('dashboard_docs');
    if (cached) {
      try {
        const parsed = JSON.parse(cached);

        // ✅ remove invalid items
        const cleaned = parsed.filter((d: Document) => d && d.id);

        setDocuments(cleaned);
        setCurrentPage(1);
      } catch {}
    }
}, []);

  const [stats, setStats] = useState<Stats>(computeStats([]));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    setStats(computeStats(documents));
  }, [documents]);

  useEffect(() => {
    let isMounted = true;
    let intervalId: number | null = null;
    let isFirstLoad = true;

    const loadStats = async () => {
      if (!isMounted) return;
      setError(null);
      

      const API_BASE =
        (import.meta as any).env?.VITE_API_BASE_URL ||
        (import.meta as any).env?.VITE_API_URL ||
        'http://localhost:8000';
      try {
        const docsRes = await fetch(`${API_BASE}/api/documents?page=1&limit=100`)
          .then(res => {
            if (!res.ok) throw new Error(`Failed: ${res.status}`);
            return res.json();
          });

        const backendDocs = docsRes.items || [];
        const backendIds = new Set(backendDocs.map((d: Document) => String(d.id)));


        setDocuments(() => {
          // ✅ ONLY USE BACKEND DATA (NO OLD CACHE MERGE)
          sessionStorage.setItem('dashboard_docs', JSON.stringify(backendDocs));

          return backendDocs;
        });



        // Stats are recomputed below when documents change
      } catch (e: any) {
        if (!isMounted) return;
        setError(e.message || 'Failed to load data');
        console.error('Dashboard fetch error:', e);
      } finally {
        
        if (isMounted) {
          setLoading(false);
          isFirstLoad = false;
        }

      }
    };

    loadStats().catch(() => {});
    intervalId = window.setInterval(() => loadStats().catch(() => {}), 25000);

    return () => {
      isMounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  const handleView = (doc: Document) => {
    if (doc.status === 'completed') {
      navigate(`/results/${String(doc.id)}`);
    } else {
      navigate(`/edit/${String(doc.id)}`, {
        state: { document: doc }
      });
    }
  };
  const getStatusBadge = (status: string) => {
    const STATUS_META: Record<string, { label: string; badgeCls: string; icon: React.ReactNode }> = {
      new: { label: 'New', badgeCls: 'bg-indigo-100 text-indigo-700 border-indigo-300', icon: <Layers className="w-3.5 h-3.5" /> },
      Uploading: { label: 'Uploading', badgeCls: 'bg-orange-100 text-orange-700 border-orange-300', icon: <Loader className="w-3.5 h-3.5 animate-spin" /> },
      uploading: { label: 'Uploading', badgeCls: 'bg-orange-100 text-orange-700 border-orange-300', icon: <Loader className="w-3.5 h-3.5 animate-spin" /> },
      processing: { label: 'Processing', badgeCls: 'bg-blue-100 text-blue-700 border-blue-300', icon: <Loader className="w-3.5 h-3.5 animate-spin" /> },
      ready_for_processing: { label: 'Ready for Processing', badgeCls: 'bg-pink-100 text-pink-700 border-pink-300', icon: <Play className="w-3.5 h-3.5" /> },
      completed: { label: 'Completed', badgeCls: 'bg-emerald-100 text-emerald-700 border-emerald-300', icon: <CheckCircle className="w-3.5 h-3.5" /> },
      failed: { label: 'Failed', badgeCls: 'bg-red-100 text-red-700 border-red-300', icon: <AlertCircle className="w-3.5 h-3.5" /> },
    };

    const meta = STATUS_META[status as keyof typeof STATUS_META] || { label: status, badgeCls: 'bg-slate-100 text-slate-700 border-slate-300', icon: <Layers className="w-3.5 h-3.5" /> };
    return (
      <Badge variant="outline" className={`${meta.badgeCls} flex items-center gap-1`}>
        {meta.icon} {meta.label}
      </Badge>
    );
  };

  // Pagination logic
  const totalPages = Math.ceil(documents.length / docsPerPage);
  const startIdx = (currentPage - 1) * docsPerPage;
  const paginatedDocs = documents.slice(startIdx, startIdx + docsPerPage);
  
  const handlePrevPage = () => {
    if (currentPage > 1) setCurrentPage(currentPage - 1);
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) setCurrentPage(currentPage + 1);
  };

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 page-hero-container text-white shadow-md">
          <h1 className="page-hero-title">Dashboard</h1>
          <p className="page-hero-subtitle text-indigo-100">
            Welcome back! Here's an overview of your document automation.
          </p>
        </div>

        
        {error ? (
          <div className="text-center py-10 text-red-500">{error}</div>
        ) : (
          <>
        
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <Card className="border-indigo-100 shadow-lg hover:shadow-xl transition-shadow bg-gradient-to-br from-white to-indigo-50">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm text-slate-700">Total Documents</CardTitle>
                  <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center">
                    <FileText className="w-4 h-4 text-white" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">{stats.total}</div>
                  <p className="text-xs text-slate-600">All uploaded documents</p>
                </CardContent>
              </Card>

              <Card className="border-blue-100 shadow-lg hover:shadow-xl transition-shadow bg-gradient-to-br from-white to-blue-50">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm text-slate-700">Processing</CardTitle>
                  <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg flex items-center justify-center">
                    <Clock className="w-4 h-4 text-white" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent">{stats.processing}</div>
                  <p className="text-xs text-slate-600">Currently in progress</p>
                </CardContent>
              </Card>

              <Card className="border-emerald-100 shadow-lg hover:shadow-xl transition-shadow bg-gradient-to-br from-white to-emerald-50">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm text-slate-700">Completed</CardTitle>
                  <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-lg flex items-center justify-center">
                    <CheckCircle className="w-4 h-4 text-white" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold bg-gradient-to-r from-emerald-600 to-teal-600 bg-clip-text text-transparent">{stats.completed}</div>
                  <p className="text-xs text-slate-600">Ready to download</p>
                </CardContent>
              </Card>
            </div>

            <div className="flex justify-between items-center mt-8">
              <h2 className="text-xl text-slate-900 font-semibold">Recent Documents</h2>
              <div className="flex gap-3">
                <Button onClick={() => navigate('/upload')} className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-md">
                  <Upload className="w-4 h-4 mr-2" />
                  Upload Document
                </Button>
                <Button variant="outline" onClick={() => navigate('/library')} className="border-indigo-200 text-indigo-700 hover:bg-indigo-50">
                  View Library
                </Button>
              </div>
            </div>

            <Card className="border-indigo-100 shadow-lg bg-white/80 backdrop-blur-sm mt-4">
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gradient-to-r from-indigo-50 to-purple-50 border-b border-indigo-100">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs text-indigo-700 uppercase tracking-wider font-semibold">
                          Document Name
                        </th>
                        <th className="px-3 py-2 text-left text-xs text-slate-600 uppercase tracking-wider">
                          Type
                        </th>
                        <th className="px-3 py-2 text-left text-xs text-slate-600 uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-3 py-2 text-left text-xs text-slate-600 uppercase tracking-wider">
                          Date
                        </th>
                        <th className="px-6 py-3 text-left text-xs text-slate-600 uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {paginatedDocs.length > 0 ? (
                        paginatedDocs.map((doc) => (
                          <tr key={doc.id} className="hover:bg-slate-50">
                            <td className="px-2 py-2">
                              <div className="flex items-center gap-2">
                                <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                                <div className="min-w-0">
                                  <div className="text-xs text-slate-900 truncate">{doc.name}</div>
                                  <div className="text-xs text-slate-500">{doc.size}</div>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-2 text-xs text-slate-700">
                              {doc.fileType}
                            </td>
                            <td className="px-3 py-2">
                              {getStatusBadge(doc.status)}
                            </td>
                            <td className="px-3 py-2 text-xs text-slate-600">
                              {doc.createdDate ? new Date(doc.createdDate).toLocaleDateString() : ''}
                            </td>
                            <td className="px-3 py-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleView(doc)}
                                className="text-slate-700 hover:text-slate-900"
                              >
                                View
                                <ArrowRight className="w-4 h-4 ml-1" />
                              </Button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5} className="px-3 py-8 text-center text-sm text-slate-500">
                            No documents uploaded yet. Upload a document to see it here.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3 mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrevPage}
                  disabled={currentPage === 1}
                  className="text-xs"
                >
                  Previous
                </Button>
                <div className="flex items-center gap-1">
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`px-2 py-1 text-xs rounded transition-all ${
                        currentPage === page
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      {page}
                    </button>
                  ))}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNextPage}
                  disabled={currentPage === totalPages}
                  className="text-xs"
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
