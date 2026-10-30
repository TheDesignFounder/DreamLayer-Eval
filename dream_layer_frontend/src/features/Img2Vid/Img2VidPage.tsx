import React, { useState, useEffect } from 'react';
import Accordion from '@/components/Accordion';
import PromptInput from '@/components/PromptInput';
import VideoModelSettings from '@/components/VideoModelSettings';
import VideoPreview from '@/components/tabs/img2vid/VideoPreview';
import { useIsMobile } from '@/hooks/use-mobile';
import { useToast } from '@/hooks/use-toast';
import { Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useImg2VidGalleryStore } from '@/stores/useImg2VidGalleryStore';
import { Txt2VidCoreSettings, defaultTxt2VidSettings } from '@/types/generationSettings';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface Img2VidPageProps {
  selectedModel: string;
  onTabChange: (tabId: string) => void;
}

const Img2VidPage: React.FC<Img2VidPageProps> = ({ selectedModel, onTabChange }) => {
  const [coreSettings, setCoreSettings] = useState<Txt2VidCoreSettings>({
    ...defaultTxt2VidSettings,
    runway_mode: 'img2vid' // Default to img2vid mode
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [runwayCredits, setRunwayCredits] = useState(0);
  const [inputImage, setInputImage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const isMobile = useIsMobile();
  const { toast } = useToast();
  const addVideos = useImg2VidGalleryStore(state => state.addVideos);
  const setLoading = useImg2VidGalleryStore(state => state.setLoading);
  const loadFromDatabase = useImg2VidGalleryStore(state => state.loadFromDatabase);

  // Parse selectedModel to determine provider
  useEffect(() => {
    if (selectedModel === 'luma') {
      updateCoreSettings({
        model: 'luma'
      });
    } else if (selectedModel === 'runway') {
      updateCoreSettings({
        model: 'runway',
        runway_mode: 'img2vid'
      });
    }
  }, [selectedModel]);

  // Load generation history from database on mount
  useEffect(() => {
    loadFromDatabase();
  }, [loadFromDatabase]);

  // Check for image from session storage (from "Send to" button)
  useEffect(() => {
    const loadImageFromUrl = async () => {
      const storedImageUrl = window.sessionStorage.getItem('img2vidImageUrl');
      if (storedImageUrl) {
        try {
          // Fetch the image from the URL
          const imageBlob = await fetch(storedImageUrl).then(r => r.blob());

          // Convert to base64
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64String = reader.result as string;
            setInputImage(base64String);
            updateCoreSettings({ input_image: base64String });
          };
          reader.readAsDataURL(imageBlob);

          // Clear the session storage after loading
          window.sessionStorage.removeItem('img2vidImageUrl');
        } catch (error) {
          console.error('Error loading image from URL:', error);
          window.sessionStorage.removeItem('img2vidImageUrl');
        }
      }
    };

    loadImageFromUrl();
  }, []);

  const updateCoreSettings = (updates: Partial<Txt2VidCoreSettings>) => {
    setCoreSettings(prev => ({ ...prev, ...updates }));
  };

  const handlePromptChange = (value: string) => {
    updateCoreSettings({ prompt: value });
  };

  const handleCopyPrompt = () => {
    const promptTextarea = document.querySelector('textarea[placeholder="Enter your video prompt here (optional)"]') as HTMLTextAreaElement;

    if (promptTextarea) {
      navigator.clipboard.writeText(promptTextarea.value);
      toast({
        title: "Copied",
        description: "Prompt copied to clipboard"
      });
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      processImageFile(file);
    }
  };

  const processImageFile = (file: File) => {
    // Check file size (10MB limit)
    if (file.size > 10 * 1024 * 1024) {
      toast({
        title: "Error",
        description: "File size must be less than 10MB",
        variant: "destructive"
      });
      return;
    }

    // Check file type
    if (!file.type.startsWith('image/')) {
      toast({
        title: "Error",
        description: "Please upload an image file (PNG, JPG, WEBP, or GIF)",
        variant: "destructive"
      });
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64String = reader.result as string;
      setInputImage(base64String);
      updateCoreSettings({ input_image: base64String });
    };
    reader.readAsDataURL(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      processImageFile(file);
    }
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleGenerateVideo = async () => {
    // Handle interrupt if already generating
    if (isGenerating) {
      await fetch('http://localhost:5008/api/txt2vid/interrupt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      setIsGenerating(false);
      setLoading(false);
      return;
    }

    if (!inputImage) {
      toast({
        title: "Error",
        description: "Please upload an image first",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsGenerating(true);
      setLoading(true);

      // Prepare the request data based on model
      const requestData: Record<string, unknown> = {
        prompt: coreSettings.prompt || '',
        provider: coreSettings.model  // Only 'runway' for img2vid (Luma requires CDN URL)
      };

      if (coreSettings.model === 'runway') {
        requestData.runway_mode = 'img2vid';
        requestData.ratio = coreSettings.ratio;
        requestData.duration = coreSettings.duration;
        requestData.input_image = inputImage;
        requestData.audio = coreSettings.audio || false;

        if (coreSettings.seed && coreSettings.seed !== -1) {
          requestData.seed = coreSettings.seed;
        }
        if (coreSettings.runway_model) {
          requestData.runway_model = coreSettings.runway_model;
        }
      }

      console.log('Sending video generation request:', requestData);

      const response = await fetch('http://localhost:5008/api/txt2vid', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      console.log('Response status:', response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Error response:', errorText);
        throw new Error(`Failed to generate video: ${errorText}`);
      }

      const data = await response.json();
      console.log('Response data:', data);

      if (data.status === 'success' && data.filename) {
        const videoUrl = `http://localhost:5008/api/videos/${data.filename}`;

        const newVideo = {
          id: `${Date.now()}-${Math.random()}`,
          url: videoUrl,
          filename: data.filename,
          prompt: coreSettings.prompt || '',
          timestamp: Date.now(),
          settings: { ...coreSettings },
          run_id: data.run_id || undefined
        };

        addVideos([newVideo]);

        toast({
          title: "Success",
          description: "Video generated successfully!"
        });
      } else {
        throw new Error(data.message || 'Failed to generate video');
      }
    } catch (error: unknown) {
      console.error('Error generating video:', error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : 'Failed to generate video',
        variant: "destructive"
      });
    } finally {
      setIsGenerating(false);
      setLoading(false);
    }
  };

  const ActionButtons = () => {
    const isLumaSelected = coreSettings.model === 'luma';
    return (
      <div className="flex items-center space-x-2">
        <Button
          className={cn(
            "px-6",
            isGenerating && "bg-red-500 hover:bg-red-600"
          )}
          onClick={handleGenerateVideo}
          disabled={isGenerating || isLumaSelected}
          title={isLumaSelected ? "Luma AI is not supported for img2vid" : ""}
        >
          {isGenerating ? 'Generating...' : 'Generate Video'}
        </Button>
      </div>
    );
  };

  const MobileVideoPreview = () => (
    <div className="my-4 w-full">
      <VideoPreview onTabChange={onTabChange} />
    </div>
  );

  return (
    <div className={`mb-4 ${isMobile ? 'grid grid-cols-1' : 'grid gap-6 md:grid-cols-[1.8fr_1fr]'}`}>
      {/* Left Column - Controls */}
      <div className="space-y-4">
        <div className="flex flex-col">
          <div className="mb-[18px] flex flex-col space-y-2 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
            <h3 className="text-base font-medium">Image-to-Video Generation Settings</h3>
            <ActionButtons />
          </div>

          {isMobile && <MobileVideoPreview />}

          <Accordion title="Core Generation Settings" number="1" defaultOpen={true}>
            {/* Image Upload Section */}
            <div className="space-y-4">
              <h4 className="text-sm font-bold text-[#2563EB]">1. Input Image</h4>
              {!inputImage ? (
                <div className="flex items-center justify-center w-full">
                  <div
                    className={cn(
                      "p-6 border-2 border-dashed rounded-md text-center flex flex-col items-center justify-center bg-card transition-colors",
                      isDragging ? "border-primary bg-primary/5" : "border-border"
                    )}
                    style={{ width: '330px', height: '330px' }}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                  >
                    <p className="text-muted-foreground mb-2 text-sm">Drag & drop an image here</p>
                    <p className="text-xs text-muted-foreground mb-4">PNG, JPG, WEBP or GIF up to 10MB</p>
                    <div className="inline-block">
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={handleBrowseClick}
                      >
                        Browse Files
                      </Button>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        onChange={handleImageUpload}
                        className="hidden"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="relative aspect-video bg-black rounded-lg overflow-hidden">
                    <img
                      src={inputImage}
                      alt="Input"
                      className="w-full h-full object-contain"
                    />
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setInputImage(null);
                      updateCoreSettings({ input_image: undefined });
                    }}
                    className="w-full"
                  >
                    Remove Image
                  </Button>
                </div>
              )}

              {/* Prompt Input */}
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-bold text-[#2563EB]">2. Prompt Input (Optional)</h4>
                <Button
                  onClick={handleCopyPrompt}
                  variant="outline"
                  size="sm"
                  className="text-xs px-2 py-1 h-auto flex items-center gap-1"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy Prompt
                </Button>
              </div>
              <PromptInput
                label="Video Prompt"
                maxLength={1000}
                placeholder="Enter your video prompt here (optional)"
                showBatchPrompts={false}
                value={coreSettings.prompt}
                onChange={handlePromptChange}
              />

              <h4 className="mb-2 mt-6 text-sm font-bold text-[#2563EB]">
                3. Video Model Settings
                {coreSettings.model === 'runway' && (
                  <span> ({runwayCredits} Credits)</span>
                )}
              </h4>
              <VideoModelSettings
                model={coreSettings.model}
                lumaModel={coreSettings.luma_model}
                aspectRatio={coreSettings.aspect_ratio}
                loop={coreSettings.loop}
                resolution={coreSettings.resolution}
                runwayMode={coreSettings.runway_mode}
                runwayModel={coreSettings.runway_model}
                ratio={coreSettings.ratio}
                duration={coreSettings.duration}
                seed={coreSettings.seed}
                audio={coreSettings.audio}
                inputImage={coreSettings.input_image}
                onModelChange={(model) => updateCoreSettings({ model })}
                onLumaModelChange={(lumaModel) => updateCoreSettings({ luma_model: lumaModel as typeof coreSettings.luma_model })}
                onAspectRatioChange={(aspectRatio) => updateCoreSettings({ aspect_ratio: aspectRatio as typeof coreSettings.aspect_ratio })}
                onLoopChange={(loop) => updateCoreSettings({ loop })}
                onResolutionChange={(resolution) => updateCoreSettings({ resolution: resolution as typeof coreSettings.resolution })}
                onRunwayModeChange={(runwayMode) => updateCoreSettings({ runway_mode: runwayMode })}
                onRunwayModelChange={(runwayModel) => updateCoreSettings({ runway_model: runwayModel as typeof coreSettings.runway_model })}
                onRatioChange={(ratio) => updateCoreSettings({ ratio: ratio as typeof coreSettings.ratio })}
                onDurationChange={(duration) => updateCoreSettings({ duration: duration as typeof coreSettings.duration })}
                onSeedChange={(seed) => updateCoreSettings({ seed })}
                onAudioChange={(audio) => updateCoreSettings({ audio })}
                onInputImageChange={(image) => updateCoreSettings({ input_image: image })}
                onCreditsCalculated={(credits) => setRunwayCredits(credits)}
              />
            </div>
          </Accordion>
        </div>
      </div>

      {/* Right Column - Preview */}
      {!isMobile && (
        <div>
          <VideoPreview onTabChange={onTabChange} />
        </div>
      )}
    </div>
  );
};

export default Img2VidPage;
