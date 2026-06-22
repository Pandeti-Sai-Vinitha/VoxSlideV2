import { useState, useEffect } from 'react';
// Utility to update status in backend
async function updateDocumentStatus(documentId: string, status: string) {
  const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
  await fetch(`${API_BASE}/api/documents/${documentId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(status)
  });
}
import { useNavigate, useParams } from 'react-router-dom';
import { CheckCircle, Clock, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import type { Document, ProcessingStep } from '../App';

interface ProcessingPageProps {
  getDocument: (id: string | undefined) => Document | null;
}

export default function ProcessingPage({ getDocument }: ProcessingPageProps) {
  const { id } = useParams();
  const document = getDocument(id);
  const navigate = useNavigate();
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [steps, setSteps] = useState<ProcessingStep[]>([
    { id: '1', name: 'Parsing Document', status: 'pending' },
    { id: '2', name: 'Generating Slides', status: 'pending' },
    { id: '3', name: 'Generating Audio', status: 'pending' },
    { id: '4', name: 'Creating PPTX', status: 'pending' },
    { id: '5', name: 'Rendering Video', status: 'pending' }
  ]);
  const [activityLog, setActivityLog] = useState<string[]>([]);

  useEffect(() => {
    // Set status to 'processing' when page loads
    if (id) updateDocumentStatus(id, 'processing');

    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          // Set status to 'completed' when done
          if (id) updateDocumentStatus(id, 'completed');
          setTimeout(() => navigate(`/results/${id}`), 1000);
          return 100;
        }
        return prev + 2;
      });
    }, 200);

    return () => clearInterval(interval);
  }, [id, navigate]);

  useEffect(() => {
    const interval = setInterval(() => {
      setSteps(prevSteps => {
        const allCompleted = prevSteps.every(s => s.status === 'completed');
        if (allCompleted) return prevSteps;

        return prevSteps.map(step => {
          if (step.status === 'completed') return step;
          if (step.status === 'pending') {
            const shouldStart = Math.random() > 0.7;
            if (shouldStart) {
              setActivityLog(prev => [...prev, `${new Date().toLocaleTimeString()} - Started ${step.name}`]);
              return { ...step, status: 'running' as const };
            }
          }
          if (step.status === 'running') {
            const shouldComplete = Math.random() > 0.6;
            if (shouldComplete) {
              const duration = `${(Math.random() * 3 + 2).toFixed(1)}s`;
              setActivityLog(prev => [...prev, `${new Date().toLocaleTimeString()} - Completed ${step.name}`]);
              return { ...step, status: 'completed' as const, duration };
            }
          }
          return step;
        });
      });
    }, 800);

    return () => clearInterval(interval);
  }, []);

  const getStepIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-6 h-6 text-emerald-600" />;
      case 'running':
        return <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />;
      default:
        return <Clock className="w-6 h-6 text-slate-400" />;
    }
  };

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 page-hero-container text-white shadow-xl">
          <h1 className="page-hero-title">Processing Document</h1>
          <p className="page-hero-subtitle text-blue-100">
            Your document is being processed in parallel. This may take a few minutes.
          </p>
        </div>

        <Card className="border-indigo-100 shadow-lg bg-white/80 backdrop-blur-sm">
          <CardHeader className="bg-gradient-to-r from-indigo-50 to-purple-50">
            <CardTitle className="text-slate-900">Overall Progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="h-3 bg-gradient-to-r from-indigo-100 to-purple-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-600 to-purple-600 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex justify-between text-sm text-slate-700">
              <span className="font-medium">Processing...</span>
              <span className="font-semibold">{progress}% Complete</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-slate-900">Parallel Processing Pipeline</CardTitle>
            <p className="text-sm text-slate-600">Multiple tasks running concurrently</p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {steps.map((step) => (
                <div
                  key={step.id}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    step.status === 'completed'
                      ? 'bg-emerald-50 border-emerald-200'
                      : step.status === 'running'
                      ? 'bg-blue-50 border-blue-300 shadow-md'
                      : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">{getStepIcon(step.status)}</div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-slate-900 truncate">{step.name}</h3>
                      <p className="text-sm text-slate-600 mt-1">
                        {step.status === 'completed' && `Done in ${step.duration || '3.2s'}`}
                        {step.status === 'running' && 'Processing...'}
                        {step.status === 'pending' && 'Queued'}
                      </p>
                      {step.status === 'running' && (
                        <div className="mt-2">
                          <div className="h-1.5 bg-blue-200 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-600 rounded-full animate-pulse" style={{ width: '60%' }}></div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-indigo-100 shadow-lg bg-white/80 backdrop-blur-sm">
          <CardHeader className="bg-gradient-to-r from-indigo-50 to-purple-50">
            <CardTitle className="text-slate-900">Activity Log</CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-40">
              <div className="space-y-2 text-sm font-mono">
                {activityLog.map((log, index) => (
                  <div key={index} className="text-slate-700 bg-slate-50 px-2 py-1 rounded">
                    {log}
                  </div>
                ))}
                {activityLog.length === 0 && (
                  <div className="text-slate-400">Initializing parallel processing...</div>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-slate-800">
            <strong className="text-blue-700">Note:</strong> Do not close this page while processing is in progress.
            You will be automatically redirected when complete.
          </p>
        </div>
      </div>
    </div>
  );
}
