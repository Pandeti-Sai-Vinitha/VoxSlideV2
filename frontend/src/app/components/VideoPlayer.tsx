import { useState, useRef, useEffect } from 'react';
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Video,
  MessageSquare,
  X,
  BookOpen,
  Settings,
} from 'lucide-react';
import { Button } from './ui/button';
import { Slider } from './ui/slider';
import { designTokens } from '../design-system';
import ChatPanel from './ChatPanel';
import AssignmentPanel from './AssignmentPanel';

// Add animation styles
const animationStyles = `
  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
`;
 
interface Slide {
  id: string;
  title: string;
  content: string;
  audioScript: string;
  timestamp: number;
}
 
interface VideoPlayerProps {
  slides?: Slide[];
  videoUrl?: string;
  onClose: () => void;
  docId?: string;
}
 
export default function VideoPlayer({ slides = [], videoUrl, onClose, docId }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [showChat, setShowChat] = useState(false);
  const [showAssignment, setShowAssignment] = useState(false);
  const [videoEnded, setVideoEnded] = useState(false);
 
  // Video event handlers
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
 
    const updateTime = () => setCurrentTime(video.currentTime);
    const updateDuration = () => setDuration(video.duration);
    const handleVideoEnd = () => setVideoEnded(true);
 
    video.addEventListener('timeupdate', updateTime);
    video.addEventListener('loadedmetadata', updateDuration);
    video.addEventListener('ended', handleVideoEnd);
 
    return () => {
      video.removeEventListener('timeupdate', updateTime);
      video.removeEventListener('loadedmetadata', updateDuration);
      video.removeEventListener('ended', handleVideoEnd);
    };
  }, []);
 
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle space if not in chat input
      if (e.code === 'Space' && !showChat && !showAssignment) {
        e.preventDefault();
        togglePlay();
      }
    };
 
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPlaying, showChat, showAssignment]);
 
  useEffect(() => {
    if (!videoRef.current) return;
    videoRef.current.muted = isMuted;
    videoRef.current.volume = volume;
  }, [isMuted, volume]);
 
  useEffect(() => {
    if (!videoRef.current) return;
    videoRef.current.playbackRate = playbackSpeed;
  }, [playbackSpeed]);
 
  // Track current slide based on video timestamp
  useEffect(() => {
    const slideIndex = slides.findIndex((slide, index) => {
      const nextSlide = slides[index + 1];
      return currentTime >= slide.timestamp && (!nextSlide || currentTime < nextSlide.timestamp);
    });
    if (slideIndex !== -1) {
      setCurrentSlideIndex(slideIndex);
    }
  }, [currentTime, slides]);
 
  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };
 
  const handleSeek = (value: number[]) => {
    if (videoRef.current) {
      videoRef.current.currentTime = value[0];
      setCurrentTime(value[0]);
    }
  };
 
  const handleVolumeChange = (value: number[]) => {
    if (videoRef.current) {
      const newVolume = value[0];
      videoRef.current.volume = newVolume;
      setVolume(newVolume);
      setIsMuted(newVolume === 0);
    }
  };
 
  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };
 
  const toggleFullscreen = () => {
    if (videoRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        videoRef.current.requestFullscreen();
      }
    }
  };
 
  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };
 
  return (
    <div className={designTokens.components.videoPlayer.container}>
      <style>{animationStyles}</style>
      <div className="min-h-screen flex flex-col h-full">
        {/* Header */}
        <div className={designTokens.components.videoPlayer.header}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center">
              <Video className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-white font-semibold">Video Presentation</h2>
              <p className="text-sm text-indigo-200">
                Total Duration: {formatTime(duration)}
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="text-white hover:bg-white/10"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>
 
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Video Section */}
          <div className={designTokens.components.videoPlayer.videoContainer}>
            <div className="flex-1 relative flex items-center justify-center min-h-0 p-4">
              <video
                ref={videoRef}
                className="w-full max-w-full max-h-[80vh] rounded-xl"
                muted={isMuted}
                playsInline
                poster="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1920' height='1080'%3E%3Cdefs%3E%3ClinearGradient id='grad' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' style='stop-color:%235b21b6;stop-opacity:1' /%3E%3Cstop offset='100%25' style='stop-color:%239333ea;stop-opacity:1' /%3E%3C/linearGradient%3E%3C/defs%3E%3Crect fill='url(%23grad)' width='1920' height='1080'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='white' font-size='64' font-family='Arial'%3EVideo Preview%3C/text%3E%3C/svg%3E"
              >
                <source src={videoUrl} type="video/mp4" />
              </video>
 
              {/* Play Overlay */}
              {!isPlaying && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/20">
                  <button
                    onClick={togglePlay}
                    className="w-20 h-20 bg-white/90 hover:bg-white rounded-full flex items-center justify-center transition-all hover:scale-110 shadow-2xl"
                  >
                    <Play className="w-10 h-10 text-indigo-600 ml-1" />
                  </button>
                </div>
              )}
 
              {/* Video Controls */}
              <div className={`absolute bottom-0 left-0 right-0 ${designTokens.components.videoPlayer.controlsGradient} p-6`}>
                <div className="space-y-4">
                  {/* Progress Bar */}
                  <div className="flex items-center gap-3 group">
                    <span className="text-white text-xs font-semibold min-w-[40px] tabular-nums">
                      {formatTime(currentTime)}
                    </span>
                    <div className="flex-1">
                      <input
                        type="range"
                        min="0"
                        max={duration || 100}
                        step="0.1"
                        value={currentTime}
                        onChange={(e) => {
                          const newTime = parseFloat(e.target.value);
                          if (videoRef.current) videoRef.current.currentTime = newTime;
                          setCurrentTime(newTime);
                        }}
                        className="w-full h-2 bg-white/30 rounded-lg appearance-none cursor-pointer hover:h-3 transition-all [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:opacity-0 group-hover:[&::-webkit-slider-thumb]:opacity-100 [&::-webkit-slider-thumb]:transition-opacity [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:shadow-lg [&::-moz-range-track]:bg-transparent [&::-moz-range-track]:border-0"
                        style={{
                          background: `linear-gradient(to right, #6366f1 0%, #6366f1 ${(currentTime / duration) * 100}%, rgba(255,255,255,0.3) ${(currentTime / duration) * 100}%, rgba(255,255,255,0.3) 100%)`
                        }}
                      />
                    </div>
                    <span className="text-white text-xs font-semibold min-w-[40px] tabular-nums text-right">
                      {formatTime(duration)}
                    </span>
                  </div>
 
                  {/* Control Buttons */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={togglePlay}
                        className="text-white hover:bg-white/20 w-10 h-10 p-0"
                      >
                        {isPlaying ? (
                          <Pause className="w-5 h-5" />
                        ) : (
                          <Play className="w-5 h-5 ml-0.5" />
                        )}
                      </Button>
                    </div>
 
                    <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 group/volume">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={toggleMute}
                          className="text-white hover:bg-white/20 p-0 w-9 h-9"
                        >
                          {isMuted ? (
                            <VolumeX className="w-4 h-4" />
                          ) : (
                            <Volume2 className="w-4 h-4" />
                          )}
                        </Button>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.01"
                          value={isMuted ? 0 : volume}
                          onChange={(e) => handleVolumeChange([parseFloat(e.target.value)])}
                          className="w-16 h-2 bg-white/30 rounded-lg appearance-none cursor-pointer hover:h-2.5 transition-all [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:opacity-0 group-hover/volume:[&::-webkit-slider-thumb]:opacity-100 [&::-webkit-slider-thumb]:transition-opacity [&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:shadow-lg [&::-moz-range-track]:bg-transparent [&::-moz-range-track]:border-0"
                          style={{
                            background: `linear-gradient(to right, #f97316 0%, #f97316 ${(isMuted ? 0 : volume) * 100}%, rgba(255,255,255,0.3) ${(isMuted ? 0 : volume) * 100}%, rgba(255,255,255,0.3) 100%)`
                          }}
                        />
                        <span className="text-white text-xs font-semibold min-w-[20px] text-center group-hover/volume:opacity-100 opacity-60 transition-opacity">
                          {Math.round((isMuted ? 0 : volume) * 10)}
                        </span>
                      </div>
 
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowChat(!showChat)}
                        className={`text-white hover:bg-white/20 p-0 w-9 h-9 flex items-center justify-center ${
                          showChat ? 'bg-white/20' : ''
                        }`}
                        title="AI Chat Assistant"
                      >
                        <img
                          src="/icons/ai-chatbot.svg"
                          alt="AI Chat"
                          className="w-5 h-5 object-contain"
                          style={showChat ? {
                            animation: 'spin 2s linear infinite',
                          } : {}}
                        />
                      </Button>
 
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowAssignment(!showAssignment)}
                        className={`text-white hover:bg-white/20 p-0 w-9 h-9 ${
                          showAssignment ? 'bg-white/20' : ''
                        }`}
                        title="Assignment & Quiz"
                      >
                        <BookOpen className="w-4 h-4" />
                      </Button>
 
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowSettings(!showSettings)}
                        className={`text-white hover:bg-white/20 p-0 w-9 h-9 ${
                          showSettings ? 'bg-white/20' : ''
                        }`}
                        title="Playback Speed"
                      >
                        <Settings className="w-4 h-4" />
                      </Button>
 
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={toggleFullscreen}
                        className="text-white hover:bg-white/20 p-0 w-9 h-9"
                      >
                        <Maximize className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
 
              {/* Settings Panel */}
              {showSettings && (
                <div className="absolute bottom-24 left-0 right-0 bg-gradient-to-t from-black/95 via-black/85 to-transparent p-6">
                  <div className="max-w-md">
                    <h3 className="text-white font-semibold mb-4">Playback Speed</h3>
                    <div className="flex gap-2 flex-wrap">
                      {[0.5, 0.75, 1, 1.25, 1.5, 1.75, 2].map((speed) => (
                        <Button
                          key={speed}
                          size="sm"
                          onClick={() => setPlaybackSpeed(speed)}
                          className={`${
                            playbackSpeed === speed
                              ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                              : 'bg-white/20 text-white hover:bg-white/30 border-white/20'
                          }`}
                        >
                          {speed}x
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
 
          {/* Chat Panel */}
          <ChatPanel
            isOpen={showChat}
            onClose={() => setShowChat(false)}
            docId={docId}
            currentTime={currentTime}
            currentSlideIndex={currentSlideIndex}
          />
        </div>
 
        {/* Assignment Modal - Fullscreen overlay */}
        <AssignmentPanel
          isOpen={showAssignment}
          onClose={() => setShowAssignment(false)}
          docId={docId}
          videoEnded={videoEnded}
          onQuizStart={() => {}}
        />
      </div>
    </div>
  );
}
 
 