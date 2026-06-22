import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState } from 'react';
import { ThemeProvider } from 'next-themes';
import { Toaster } from './components/ui/sonner';

import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import LibraryPage from './pages/LibraryPage';
import EditPage from './pages/EditPage';
import ProcessingPage from './pages/ProcessingPage';
import ResultsPage from './pages/ResultsPage';
import SettingsPage from './pages/SettingsPage';

import AppLayout from './components/AppLayout';

/* ================= TYPES ================= */

export type DocumentStatus =
  | 'new'
  | 'uploading'
  | 'processing'
  | 'completed'
  | 'ready_for_processing'
  | 'failed';

export interface Slide {
  id: string;
  title: string;
  content: string;
  audioScript: string;
  audioUrl: string;
  status: 'pending' | 'generated' | 'editing';
  imageUrl?: string;
  imageIndex?: number | null;
  imagePrompt?: string;
}

export interface Document {
  id: string;
  name: string;
  basename?: string;
  fileType: 'PDF' | 'DOCX';
  status: DocumentStatus;
  createdDate: string;
  size: string;
  generationMode?: 'pptx' | 'video';

  slides?: Slide[];

  outputs?: {
    pptxUrl?: string;
    mp4Url?: string;
    generatedAt?: string;
  };
  output_type?: string;
}

/* ================= APP ================= */

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(true);

  const [documents, setDocuments] = useState<Document[]>([]);

  /* ================= HELPERS ================= */

  const getDocumentById = (id: string | undefined): Document | null => {
    if (!id) return null;
    return documents.find(doc => doc.id === id) || null;
  };

  const handleLogout = () => setIsAuthenticated(false);

  const addDocument = (doc: Document) => {
    setDocuments(prev => {
      const existingIndex = prev.findIndex(d => d.id === doc.id);
      if (existingIndex !== -1) {
        return prev.map(d => (d.id === doc.id ? { ...d, ...doc } : d));
      }
      return [...prev, doc];
    });
  };

  const updateDocument = (id: string, updates: Partial<Document>) => {
    setDocuments(prev =>
      prev.map(doc => (doc.id === id ? { ...doc, ...updates } : doc))
    );
  };

  const deleteDocument = (id: string) => {
    setDocuments(prev => prev.filter(doc => doc.id !== id));
  };

  /* ================= ROUTES ================= */

  return (
    <ThemeProvider attribute="class" defaultTheme="light">
      <BrowserRouter>
        <Routes>
          <Route
            path="/"
            element={
              isAuthenticated
                ? <AppLayout onLogout={handleLogout} />
                : <Navigate to="/login" />
            }
          >
            <Route index element={<Navigate to="/dashboard" />} />

            <Route path="dashboard" element={<DashboardPage documents={documents} />} />

            <Route
              path="upload"
              element={<UploadPage onUpload={addDocument} />}
            />

            <Route
              path="library"
              element={<LibraryPage documents={documents} />}
            />

            <Route
              path="edit"
              element={<EditPage onUpdate={updateDocument} />}
            />

            <Route
              path="edit/:id"
              element={
                <EditPage
                  getDocument={getDocumentById}
                  onUpdate={updateDocument}
                />
              }
            />

            <Route
              path="processing/:id"
              element={<ProcessingPage getDocument={getDocumentById} />}
            />

            <Route
              path="results/:id"
              element={<ResultsPage getDocument={getDocumentById} />}
            />

            <Route path="settings" element={<SettingsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" />} />
        </Routes>

        <Toaster />
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;