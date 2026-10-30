import React, { useState, useEffect } from 'react';
import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Button } from "@/components/ui/button";
import { useImg2VidGalleryStore } from '@/stores/useImg2VidGalleryStore';
import { Download, FolderOpen, Copy, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import VideoEvalMetrics from '@/components/VideoEvalMetrics';

interface VideoPreviewProps {
  onTabChange?: (tabId: string) => void;
}

const LoadingAnimation = () => (
  <div className="animate-pulse space-y-4">
    <div className="h-full w-full bg-muted rounded-md flex items-center justify-center">
      <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>
  </div>
);

const VideoPreview: React.FC<VideoPreviewProps> = ({ onTabChange }) => {
  const { videos, isLoading, currentVideoIndex, setCurrentVideoIndex, removeVideo } = useImg2VidGalleryStore();
  const [outputSettingsExpanded, setOutputSettingsExpanded] = useState(true);
  const [thumbnailStartIndex, setThumbnailStartIndex] = useState(0);
  const [videoMetrics, setVideoMetrics] = useState<Record<string, unknown>>({});
  const [metricsLoading, setMetricsLoading] = useState(false);

  const currentVideo = videos[currentVideoIndex] || videos[0];

  // Auto-load cached metrics when video changes
  useEffect(() => {
    if (!currentVideo || videoMetrics[currentVideo.id]) return;
    const filename = currentVideo.filename;
    if (!filename) return;
    fetch(`http://localhost:5008/api/video-metrics-cache/${encodeURIComponent(filename)}`)
      .then(res => res.json())
      .then(result => {
        if (result.status === 'success' && result.metrics) {
          setVideoMetrics(prev => ({ ...prev, [currentVideo.id]: result.metrics }));
        }
      })
      .catch(() => {}); // Silently ignore if no cache
  }, [currentVideo?.id]);

  const maxThumbnails = 5;
  const totalPages = Math.ceil(videos.length / maxThumbnails);
  const currentPage = Math.floor(thumbnailStartIndex / maxThumbnails) + 1;

  const handleDownload = async () => {
    if (!currentVideo) return;

    try {
      const response = await fetch(currentVideo.url);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = currentVideo.filename || `video_${currentVideo.id}.mp4`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error downloading video:', error);
    }
  };

  const handleShowInFolder = async () => {
    try {
      console.log('Opening videos folder...');
      const response = await fetch('http://localhost:5008/api/open-videos-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const result = await response.json();
      console.log(result.message || 'Videos folder opened');
    } catch (error) {
      console.error('Error opening videos folder:', error);
    }
  };

  const handleCopyOutputSettings = () => {
    if (!currentVideo?.settings) return;

    const settingsText = JSON.stringify(currentVideo.settings, null, 2);
    navigator.clipboard.writeText(settingsText);
  };

  const handlePrevThumbnails = () => {
    setThumbnailStartIndex(Math.max(0, thumbnailStartIndex - maxThumbnails));
  };

  const handleNextThumbnails = () => {
    const newStartIndex = thumbnailStartIndex + maxThumbnails;
    if (newStartIndex < videos.length) {
      setThumbnailStartIndex(newStartIndex);
    }
  };

  const handleThumbnailClick = (index: number) => {
    const actualIndex = thumbnailStartIndex + index;
    setCurrentVideoIndex(actualIndex);
  };

  const handleCalculateVideoMetrics = async () => {
    if (!currentVideo) return;
    setMetricsLoading(true);
    try {
      const response = await fetch('http://localhost:5008/api/calculate-video-metrics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_url: currentVideo.filename,
          prompt: currentVideo.prompt || '',
          run_id: currentVideo.run_id || '',
        }),
      });
      const result = await response.json();
      if (result.status === 'success' && result.metrics) {
        setVideoMetrics(prev => ({ ...prev, [currentVideo.id]: result.metrics }));
      }
    } catch (error) {
      console.error('Error calculating video metrics:', error);
    } finally {
      setMetricsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Main Video Display */}
      <AspectRatio ratio={16/9} className="w-full">
        <div className="flex h-full w-full flex-col items-center justify-center rounded-md border border-border bg-card p-4">
          {isLoading ? (
            <LoadingAnimation />
          ) : videos.length > 0 && currentVideo ? (
            <div className="w-full h-full">
              <video
                src={currentVideo.url}
                controls
                className="w-full h-full object-contain rounded-md"
                key={currentVideo.id}
              >
                Your browser does not support the video tag.
              </video>
            </div>
          ) : (
            <>
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-md bg-secondary">
                <svg
                  viewBox="0 0 24 24"
                  className="h-6 w-6 text-muted-foreground"
                  fill="none"
                  stroke="currentColor"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
                  <path d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5" />
                  <circle cx="12" cy="12" r="3" fill="currentColor" />
                </svg>
              </div>
              <p className="text-sm text-muted-foreground">Generated Videos Will Display Here</p>
            </>
          )}
        </div>
      </AspectRatio>

      {/* Thumbnail Navigation */}
      {videos.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-center gap-2 px-4">
            {/* Left Arrow */}
            {videos.length > maxThumbnails && (
              <Button
                variant="ghost"
                size="sm"
                className="h-16 w-8 p-0 hover:bg-accent"
                onClick={handlePrevThumbnails}
                disabled={thumbnailStartIndex === 0}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            )}

            {/* Thumbnails */}
            <div className="flex gap-2">
              {videos.slice(thumbnailStartIndex, thumbnailStartIndex + maxThumbnails).map((video, index) => {
                const actualIndex = thumbnailStartIndex + index;
                return (
                  <button
                    key={video.id}
                    onClick={() => handleThumbnailClick(index)}
                    className={`w-16 h-16 rounded border-2 transition-colors overflow-hidden ${
                      actualIndex === currentVideoIndex
                        ? 'border-primary'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <video
                      src={video.url}
                      className="w-full h-full object-cover"
                    />
                  </button>
                );
              })}

              {/* Show empty squares if less than maxThumbnails videos in current page */}
              {videos.slice(thumbnailStartIndex, thumbnailStartIndex + maxThumbnails).length < maxThumbnails &&
               thumbnailStartIndex + maxThumbnails >= videos.length &&
               Array.from({
                 length: maxThumbnails - videos.slice(thumbnailStartIndex, thumbnailStartIndex + maxThumbnails).length
               }).map((_, index) => (
                <div
                  key={`empty-${index}`}
                  className="w-16 h-16 rounded"
                  style={{ backgroundColor: '#f1f1f1' }}
                />
              ))}
            </div>

            {/* Right Arrow */}
            {videos.length > maxThumbnails && (
              <Button
                variant="ghost"
                size="sm"
                className="h-16 w-8 p-0 hover:bg-accent"
                onClick={handleNextThumbnails}
                disabled={thumbnailStartIndex + maxThumbnails >= videos.length}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            )}
          </div>

          {/* Pagination Indicator */}
          {videos.length > maxThumbnails && (
            <div className="flex justify-center">
              <div className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
                {currentPage} / {totalPages}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action Sections */}
      {videos.length > 0 && currentVideo && (
        <div className="space-y-4 px-4">
          {/* Download Section */}
          <div>
            <div className="flex items-center flex-wrap gap-2">
              <span className="text-sm font-medium">Download:</span>
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-8"
                onClick={handleDownload}
              >
                <Download className="w-3 h-3 mr-1" />
                MP4
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-8"
                onClick={handleShowInFolder}
              >
                <FolderOpen className="w-3 h-3 mr-1" />
                Show in Folder
              </Button>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-border"></div>

          {/* Output Settings Section */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium">Output Settings</span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs h-8"
                  onClick={handleCopyOutputSettings}
                >
                  <Copy className="w-3 h-3 mr-1" />
                  Copy Output Settings
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setOutputSettingsExpanded(!outputSettingsExpanded)}
                >
                  <ChevronDown className={`w-4 h-4 transition-transform ${outputSettingsExpanded ? 'rotate-180' : ''}`} />
                </Button>
              </div>
            </div>

            {outputSettingsExpanded && (
              <div className="bg-muted p-3 rounded-md text-xs leading-relaxed">
                <div className="space-y-3">
                  <div>
                    <div className="font-semibold mb-1">Prompt:</div>
                    <div className="text-muted-foreground break-words">{currentVideo.prompt || 'N/A'}</div>
                  </div>

                  <div className="space-y-2">
                    <div><strong>Model:</strong> {currentVideo.settings?.model || 'N/A'}</div>
                    {currentVideo.settings?.model === 'luma' && (
                      <>
                        <div><strong>Aspect Ratio:</strong> {currentVideo.settings?.aspect_ratio || 'N/A'}</div>
                        <div><strong>Loop:</strong> {currentVideo.settings?.loop ? 'Yes' : 'No'}</div>
                        <div><strong>Resolution:</strong> {currentVideo.settings?.resolution || 'N/A'}</div>
                      </>
                    )}
                    {currentVideo.settings?.model === 'runway' && (
                      <>
                        <div><strong>Mode:</strong> {currentVideo.settings?.runway_mode || 'N/A'}</div>
                        <div><strong>Ratio:</strong> {currentVideo.settings?.ratio || 'N/A'}</div>
                        <div><strong>Duration:</strong> {currentVideo.settings?.duration || 'N/A'}s</div>
                        {currentVideo.settings?.seed && currentVideo.settings.seed !== -1 && (
                          <div><strong>Seed:</strong> {currentVideo.settings.seed}</div>
                        )}
                      </>
                    )}
                    <div><strong>Filename:</strong> {currentVideo.filename}</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="border-t border-border"></div>

          {/* Video Evaluation Metrics */}
          <VideoEvalMetrics
            videoId={currentVideo.id}
            videoPath={currentVideo.url}
            prompt={currentVideo.prompt}
            metrics={videoMetrics[currentVideo.id]}
            isLoading={metricsLoading}
            onCalculateMetrics={handleCalculateVideoMetrics}
          />
        </div>
      )}
    </div>
  );
};

export default VideoPreview;
