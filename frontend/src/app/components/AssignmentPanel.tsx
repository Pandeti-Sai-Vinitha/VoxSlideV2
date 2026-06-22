import { useState } from 'react';
import {
  BookOpen,
  CheckCircle2,
  XCircle,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  X,
  Loader,
} from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { designTokens, formatScore } from '../design-system';

interface QuizQuestion {
  id: number;
  type: 'mcq' | 'true_false';
  question: string;
  options?: string[];
  correctAnswer?: string | boolean;
}

interface AssignmentPanelProps {
  isOpen: boolean;
  onClose: () => void;
  docId?: string;
  videoEnded: boolean;
  onQuizStart: (mode: 'assignment' | 'test') => void;
}

export default function AssignmentPanel({
  isOpen,
  onClose,
  docId,
  videoEnded,
  onQuizStart,
}: AssignmentPanelProps) {
  const [quizMode, setQuizMode] = useState<'none' | 'assignment' | 'test'>('none');
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [userAnswers, setUserAnswers] = useState<{ [key: number]: string }>({});
  const [quizComplete, setQuizComplete] = useState(false);
  const [score, setScore] = useState(0);
  const [isGeneratingQuiz, setIsGeneratingQuiz] = useState(false);

  const handleStartQuiz = async (mode: 'assignment' | 'test') => {
    setIsGeneratingQuiz(true);
    setQuizMode(mode);

    try {
      const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
      const resp = await fetch(`${API_BASE}/agent/get-quiz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_id: docId || '',
          quiz_type: mode,
          num_questions: 5,
        }),
      });

      if (!resp.ok) throw new Error(`Quiz fetch error ${resp.status}`);

      const data = await resp.json();
      setQuizQuestions(data.questions || []);
      setCurrentQuestionIndex(0);
      setUserAnswers({});
      setQuizComplete(false);
      onQuizStart(mode);
    } catch (err) {
      console.error('Failed to fetch quiz from backend:', err);
      // No fallback - show error to user
      setQuizMode('none');
      alert('Failed to generate quiz. Please try again.');
    } finally {
      setIsGeneratingQuiz(false);
    }
  };

  const submitAnswer = (answer: string) => {
    const newAnswers = { ...userAnswers, [currentQuestionIndex]: answer };
    setUserAnswers(newAnswers);

    if (currentQuestionIndex < quizQuestions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    } else {
      // Calculate score - only for MCQ and True/False questions
      let correctCount = 0;
      let scorableQuestions = 0;

      quizQuestions.forEach((q, idx) => {
        if (q.type === 'mcq' || q.type === 'true_false') {
          scorableQuestions++;
          const answer = newAnswers[idx]?.toString();
          const correctAnswer = q.correctAnswer?.toString();
          if (answer === correctAnswer) {
            correctCount++;
          }
        }
      });

      const finalScore = scorableQuestions > 0 ? Math.round((correctCount / scorableQuestions) * 100) : 0;
      setScore(finalScore);
      setQuizComplete(true);
    }
  };

  const restartQuiz = () => {
    setQuizMode('none');
    setQuizQuestions([]);
    setCurrentQuestionIndex(0);
    setUserAnswers({});
    setQuizComplete(false);
    setScore(0);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] bg-white shadow-2xl border-0 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-emerald-50 to-teal-50 border-b border-emerald-200 p-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-lg flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="font-bold text-slate-900 text-lg">
                {quizMode === 'assignment' ? 'Assignment' : quizMode === 'test' ? 'Test' : 'Assessment'}
              </h2>
              {quizMode !== 'none' && !quizComplete && (
                <p className="text-sm text-slate-600">
                  Question {currentQuestionIndex + 1} of {quizQuestions.length}
                </p>
              )}
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="text-slate-500 hover:text-slate-900 hover:bg-slate-100 h-8 w-8 p-0"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {quizMode === 'none' && !quizComplete && (
            <div className="space-y-6 text-center">
              {!videoEnded ? (
                <div className="space-y-4 py-12">
                  <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto">
                    <BookOpen className="w-8 h-8 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-slate-900">Finish the video first</p>
                    <p className="text-slate-600 mt-2">Complete the video to unlock the assessment</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-6 py-8">
                  <div>
                    <p className="text-lg font-semibold text-slate-900 mb-2">Choose Assessment Type</p>
                    <p className="text-slate-600">Select how you'd like to test your knowledge</p>
                  </div>

                  <div className="space-y-3">
                    <Button
                      onClick={() => handleStartQuiz('assignment')}
                      disabled={isGeneratingQuiz}
                      className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white justify-start h-auto py-4"
                    >
                      {isGeneratingQuiz ? (
                        <>
                          <Loader className="w-4 h-4 mr-3 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        <>
                          <BookOpen className="w-5 h-5 mr-3" />
                          <div className="text-left">
                            <div className="font-semibold text-base">Assignment</div>
                            <div className="text-xs text-white/80">Practice without scoring</div>
                          </div>
                        </>
                      )}
                    </Button>

                    <Button
                      onClick={() => handleStartQuiz('test')}
                      disabled={isGeneratingQuiz}
                      className="w-full bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white justify-start h-auto py-4"
                    >
                      {isGeneratingQuiz ? (
                        <>
                          <Loader className="w-4 h-4 mr-3 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        <>
                          <BookOpen className="w-5 h-5 mr-3" />
                          <div className="text-left">
                            <div className="font-semibold text-base">Test</div>
                            <div className="text-xs text-white/80">Graded assessment with scoring</div>
                          </div>
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {quizMode !== 'none' && !quizComplete && quizQuestions.length > 0 && (
            <div className="space-y-6">
              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-semibold text-slate-700">
                    Question {currentQuestionIndex + 1} of {quizQuestions.length}
                  </span>
                  <Badge variant="outline" className="bg-slate-100 text-slate-700 border-slate-300">
                    {quizMode === 'assignment' ? '📝 Assignment' : '✓ Test'}
                  </Badge>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-emerald-600 to-teal-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${((currentQuestionIndex + 1) / quizQuestions.length) * 100}%`,
                    }}
                  />
                </div>
              </div>

              {/* Question */}
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-slate-900">
                  {quizQuestions[currentQuestionIndex].question}
                </h3>

                {/* Dynamic Question Rendering Based on Type */}
                <div className="space-y-2">
                  {quizQuestions[currentQuestionIndex].type === 'mcq' && (
                    <div className="space-y-2">
                      {quizQuestions[currentQuestionIndex].options?.map((option, idx) => (
                        <button
                          key={idx}
                          onClick={() => submitAnswer(option)}
                          className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                            userAnswers[currentQuestionIndex] === option
                              ? 'border-emerald-600 bg-emerald-50'
                              : 'border-slate-200 bg-white hover:border-slate-300'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                                userAnswers[currentQuestionIndex] === option
                                  ? 'border-emerald-600 bg-emerald-600'
                                  : 'border-slate-300'
                              }`}
                            >
                              {userAnswers[currentQuestionIndex] === option && (
                                <div className="w-2 h-2 bg-white rounded-full" />
                              )}
                            </div>
                            <span className="text-base text-slate-700 font-medium">{option}</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}

                  {quizQuestions[currentQuestionIndex].type === 'true_false' && (
                    <div className="flex gap-3">
                      <button
                        onClick={() => submitAnswer('true')}
                        className={`flex-1 p-4 rounded-lg border-2 transition-all font-semibold ${
                          userAnswers[currentQuestionIndex] === 'true'
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                            : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        ✓ True
                      </button>
                      <button
                        onClick={() => submitAnswer('false')}
                        className={`flex-1 p-4 rounded-lg border-2 transition-all font-semibold ${
                          userAnswers[currentQuestionIndex] === 'false'
                            ? 'border-red-600 bg-red-50 text-red-700'
                            : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        ✗ False
                      </button>
                    </div>
                  )}
                </div>

                {/* Navigation */}
                <div className="flex gap-2 pt-4">
                  <Button
                    variant="outline"
                    onClick={() => setCurrentQuestionIndex(Math.max(0, currentQuestionIndex - 1))}
                    disabled={currentQuestionIndex === 0}
                    className="flex-1"
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    Previous
                  </Button>
                  <Button
                    onClick={() => submitAnswer(userAnswers[currentQuestionIndex] || '')}
                    disabled={!userAnswers[currentQuestionIndex]}
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    {currentQuestionIndex === quizQuestions.length - 1 ? 'Submit' : 'Next'}
                    {currentQuestionIndex < quizQuestions.length - 1 && (
                      <ChevronRight className="w-4 h-4 ml-1" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {quizComplete && (
            <div className="space-y-6">
              {/* Score Display - Only for Test */}
              {quizMode === 'test' && (
                <div className="rounded-xl p-8 text-center space-y-4 bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200">
                  <div className="space-y-3">
                    <div className="text-6xl font-bold text-emerald-600">{score}%</div>
                    <div className="text-2xl font-semibold text-slate-900">
                      {formatScore(score).level}
                    </div>
                    <div className="text-lg font-semibold text-emerald-700">
                      Grade: {formatScore(score).grade}
                    </div>
                  </div>
                  <p className="text-slate-600 text-sm">
                    You got {Object.values(userAnswers).filter((ans, idx) => ans === quizQuestions[idx]?.correctAnswer).length} out of {quizQuestions.length} questions correct
                  </p>
                </div>
              )}

              {/* For Assignment - Simple completion message */}
              {quizMode === 'assignment' && (
                <div className="rounded-xl p-8 text-center space-y-4 bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200">
                  <div className="text-5xl">✓</div>
                  <div className="space-y-2">
                    <div className="text-2xl font-semibold text-slate-900">
                      Assignment Complete!
                    </div>
                    <p className="text-slate-600">
                      Great job! You've finished the assignment practice.
                    </p>
                  </div>
                </div>
              )}

              {/* Results Summary */}
              <div className="space-y-3">
                <h4 className="font-semibold text-slate-900 text-base">Answer Review</h4>
                <div className="max-h-64 overflow-y-auto space-y-2">
                  {quizQuestions.map((question, idx) => {
                    const userAnswer = userAnswers[idx];
                    let isCorrect = false;

                    // Determine correctness based on question type
                    if (question.type === 'mcq' || question.type === 'true_false') {
                      isCorrect = userAnswer === (question.correctAnswer?.toString());
                    } else {
                      // For open-ended, short answer, and scenario questions, just mark as answered
                      isCorrect = Boolean(userAnswer);
                    }

                    return (
                      <div
                        key={idx}
                        className={`p-3 rounded-lg border ${
                          isCorrect
                            ? 'bg-emerald-50 border-emerald-200'
                            : 'bg-red-50 border-red-200'
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <div className="flex-shrink-0 mt-0.5">
                            {isCorrect ? (
                              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                            ) : (
                              <XCircle className="w-4 h-4 text-red-600" />
                            )}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <p className="text-xs font-medium text-slate-900">
                                Q{idx + 1}: {question.question.substring(0, 50)}...
                              </p>
                              <Badge variant="outline" className="text-xs px-2 py-0 capitalize">
                                {question.type.replace('_', ' ')}
                              </Badge>
                            </div>
                            <div className="text-xs text-slate-600 space-y-1 mt-1">
                              <p>
                                <span className="font-medium">Your answer:</span> {userAnswer || 'Not answered'}
                              </p>
                              {userAnswer !== question.correctAnswer && (
                                <p className="text-emerald-700">
                                  <span className="font-medium">Correct:</span> {question.correctAnswer?.toString()}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-4">
                <Button
                  onClick={onClose}
                  variant="outline"
                  className="flex-1 border-slate-300"
                >
                  Close
                </Button>
                <Button
                  onClick={restartQuiz}
                  className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Restart
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
 