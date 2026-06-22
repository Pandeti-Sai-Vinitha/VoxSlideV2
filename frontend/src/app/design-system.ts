/**
 * PPTAPP Design System
 * Centralized design tokens for consistent styling across the application
 */

export const designTokens = {
  // Color Palettes
  colors: {
    primary: {
      light: '#6366f1',
      DEFAULT: '#4f46e5',
      dark: '#4338ca',
    },
    secondary: {
      light: '#a78bfa',
      DEFAULT: '#9333ea',
      dark: '#7e22ce',
    },
    accent: {
      light: '#ec4899',
      DEFAULT: '#db2777',
      dark: '#be185d',
    },
    // Status colors
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6',

    // Gradients for sections
    gradients: {
      // Upload section - Template
      templateGradient: 'from-indigo-500 to-indigo-600',
      // Upload section - Persona
      personaGradient: 'from-amber-500 to-orange-500',
      // Upload section - Slides
      slidesGradient: 'from-cyan-500 to-blue-500',
      // Upload section - Voices
      voicesGradient: 'from-purple-500 to-pink-500',
      // Primary actions
      primaryGradient: 'from-indigo-600 to-purple-600',
      // Background
      bgGradient: 'from-slate-900 via-indigo-900 to-purple-900',
    },
  },

  // Spacing
  spacing: {
    xs: '0.25rem', // 4px
    sm: '0.5rem',  // 8px
    md: '1rem',    // 16px
    lg: '1.5rem',  // 24px
    xl: '2rem',    // 32px
    '2xl': '3rem', // 48px
  },

  // Typography
  typography: {
    // Heading styles
    h1: 'text-4xl font-bold leading-tight',
    h2: 'text-3xl font-bold leading-tight',
    h3: 'text-2xl font-semibold leading-snug',
    h4: 'text-xl font-semibold',
    h5: 'text-lg font-semibold',
    h6: 'text-base font-semibold',

    // Body text
    body: 'text-base font-normal leading-relaxed',
    bodySmall: 'text-sm font-normal leading-relaxed',
    bodySmallerSmall: 'text-xs font-normal leading-relaxed',

    // Special text
    label: 'text-sm font-medium',
    caption: 'text-xs font-medium',
  },

  // Border Radius
  borderRadius: {
    sm: '0.375rem',   // 6px
    md: '0.5rem',     // 8px
    lg: '0.75rem',    // 12px
    xl: '1rem',       // 16px
    '2xl': '1.5rem',  // 24px
    full: '9999px',
  },

  // Shadows
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
    '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
  },

  // Breakpoints (Tailwind defaults)
  breakpoints: {
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px',
  },

  // Component-specific styles
  components: {
    uploadSection: {
      header: 'bg-gradient-to-r from-indigo-600 to-purple-600 rounded-2xl p-8 text-white shadow-xl',
      card: 'border-indigo-100 shadow-lg bg-white/80 backdrop-blur-sm',
      configPanel: 'rounded-xl border-2 p-6 transition-all duration-300',
      configPanelTemplate: 'border-indigo-200 bg-gradient-to-br from-indigo-50 to-indigo-100',
      configPanelPersona: 'border-amber-200 bg-gradient-to-br from-amber-50 to-orange-100',
      configPanelSlides: 'border-cyan-200 bg-gradient-to-br from-cyan-50 to-blue-100',
      configPanelVoices: 'border-purple-200 bg-gradient-to-br from-purple-50 to-pink-100',
    },
    videoPlayer: {
      container: 'fixed inset-0 z-50 bg-gradient-to-br from-slate-900 via-indigo-900 to-purple-900 overflow-hidden',
      header: 'flex items-center justify-between p-4 bg-black/30 backdrop-blur-md border-b border-white/10',
      videoContainer: 'flex-1 flex flex-col bg-black min-h-0',
      controlsGradient: 'bg-gradient-to-t from-black/90 via-black/70 to-transparent',
      chatPanel: 'w-96 bg-white/95 backdrop-blur-md border-l border-indigo-100 flex flex-col min-h-0',
      chatHeader: 'p-4 border-b border-indigo-100 bg-gradient-to-r from-indigo-50 to-purple-50',
      assignmentPanel: 'w-96 bg-white/95 backdrop-blur-md border-l border-emerald-100 flex flex-col min-h-0',
      assignmentHeader: 'p-4 border-b border-emerald-100 bg-gradient-to-r from-emerald-50 to-teal-50',
    },
    button: {
      primary: 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white',
      secondary: 'bg-gradient-to-r from-slate-600 to-slate-700 hover:from-slate-700 hover:to-slate-800 text-white',
      ghost: 'text-white hover:bg-white/20',
    },
  },

  // Animation/Transition
  animation: {
    default: 'transition-all duration-300 ease-in-out',
    fast: 'transition-all duration-150 ease-in-out',
    slow: 'transition-all duration-500 ease-in-out',
  },
};

/**
 * Color scheme for quiz results
 */
export const quizColorScheme = {
  excellent: {
    bg: 'bg-emerald-100',
    text: 'text-emerald-900',
    border: 'border-emerald-300',
    badge: 'bg-emerald-500',
  },
  good: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-900',
    border: 'border-yellow-300',
    badge: 'bg-yellow-500',
  },
  fair: {
    bg: 'bg-orange-100',
    text: 'text-orange-900',
    border: 'border-orange-300',
    badge: 'bg-orange-500',
  },
  poor: {
    bg: 'bg-red-100',
    text: 'text-red-900',
    border: 'border-red-300',
    badge: 'bg-red-500',
  },
};

/**
 * Helper function to get quiz color scheme based on score
 */
export function getQuizColorScheme(score: number) {
  if (score >= 80) return quizColorScheme.excellent;
  if (score >= 60) return quizColorScheme.good;
  if (score >= 40) return quizColorScheme.fair;
  return quizColorScheme.poor;
}

/**
 * Helper function to format score as percentage with grade
 */
export function formatScore(score: number): { percentage: string; grade: string; level: string } {
  let grade = 'F';
  let level = 'Poor';
  if (score >= 90) {
    grade = 'A';
    level = 'Excellent';
  } else if (score >= 80) {
    grade = 'B';
    level = 'Excellent';
  } else if (score >= 70) {
    grade = 'C';
    level = 'Good';
  } else if (score >= 60) {
    grade = 'D';
    level = 'Fair';
  }
  return { percentage: `${score}%`, grade, level };
}
