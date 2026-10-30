import React, { useState, useEffect } from 'react';
import Accordion from '@/components/Accordion';
import PromptInput from '@/components/PromptInput';
import VideoModelSettings from '@/components/VideoModelSettings';
import VideoPreview from '@/components/tabs/txt2vid/VideoPreview';
import { useIsMobile } from '@/hooks/use-mobile';
import { useToast } from '@/hooks/use-toast';
import { Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useTxt2VidGalleryStore } from '@/stores/useTxt2VidGalleryStore';
import { Txt2VidCoreSettings, defaultTxt2VidSettings } from '@/types/generationSettings';

interface Txt2VidPageProps {
  selectedModel: string;
  onTabChange: (tabId: string) => void;
}

const Txt2VidPage: React.FC<Txt2VidPageProps> = ({ selectedModel, onTabChange }) => {
  const [coreSettings, setCoreSettings] = useState<Txt2VidCoreSettings>({
    ...defaultTxt2VidSettings
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [runwayCredits, setRunwayCredits] = useState(0);
  const isMobile = useIsMobile();
  const { toast } = useToast();
  const addVideos = useTxt2VidGalleryStore(state => state.addVideos);
  const setLoading = useTxt2VidGalleryStore(state => state.setLoading);
  const loadFromDatabase = useTxt2VidGalleryStore(state => state.loadFromDatabase);

  // Parse selectedModel to determine provider
  useEffect(() => {
    if (selectedModel === 'luma') {
      updateCoreSettings({
        model: 'luma'
      });
    } else if (selectedModel === 'runway') {
      updateCoreSettings({
        model: 'runway'
      });
    }
  }, [selectedModel]);

  // Load generation history from database on mount
  useEffect(() => {
    loadFromDatabase();
  }, [loadFromDatabase]);

  // Check for prompt from session storage (from img2txt "Send to" button)
  useEffect(() => {
    const storedPrompt = window.sessionStorage.getItem('txt2vidPrompt');
    if (storedPrompt) {
      updateCoreSettings({ prompt: storedPrompt });
      window.sessionStorage.removeItem('txt2vidPrompt');
    }
  }, []);

  const updateCoreSettings = (updates: Partial<Txt2VidCoreSettings>) => {
    setCoreSettings(prev => ({ ...prev, ...updates }));
  };

  const handlePromptChange = (value: string) => {
    updateCoreSettings({ prompt: value });
  };

  const handleCopyPrompt = () => {
    const promptTextarea = document.querySelector('textarea[placeholder="Enter your video prompt here"]') as HTMLTextAreaElement;

    if (promptTextarea) {
      navigator.clipboard.writeText(promptTextarea.value);
      toast({
        title: "Copied",
        description: "Prompt copied to clipboard"
      });
    }
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

    if (!coreSettings.prompt.trim()) {
      toast({
        title: "Error",
        description: "Please enter a prompt",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsGenerating(true);
      setLoading(true);

      // Prepare the request data based on model
      const requestData: Record<string, unknown> = {
        prompt: coreSettings.prompt,
        provider: coreSettings.model  // 'luma' or 'runway'
      };

      if (coreSettings.model === 'luma') {
        requestData.aspect_ratio = coreSettings.aspect_ratio;
        requestData.loop = coreSettings.loop;
        if (coreSettings.resolution) {
          requestData.resolution = coreSettings.resolution;
        }
        if (coreSettings.luma_model) {
          requestData.luma_model = coreSettings.luma_model;  // 'ray-1-6'
        }
      } else if (coreSettings.model === 'runway') {
        requestData.runway_mode = coreSettings.runway_mode || 'text2vid';
        requestData.ratio = coreSettings.ratio;
        requestData.duration = coreSettings.duration;
        requestData.audio = coreSettings.audio || false;

        if (coreSettings.runway_mode === 'img2vid' && coreSettings.input_image) {
          requestData.input_image = coreSettings.input_image;
        }

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
          prompt: coreSettings.prompt,
          timestamp: Date.now(),
          settings: {
            ...coreSettings
          },
          run_id: data.run_id || undefined
        };

        console.log('Adding video to gallery:', newVideo);
        addVideos([newVideo]);

        toast({
          title: "Success",
          description: "Video generated successfully!"
        });
      } else {
        console.error('Unexpected response format:', data);
        throw new Error('No video was generated');
      }
    } catch (error) {
      console.error('Error details:', error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to generate video",
        variant: "destructive"
      });
    } finally {
      setIsGenerating(false);
      setLoading(false);
    }
  };

  const ActionButtons = () => (
    <div className="flex space-x-2">
      <Button
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        onClick={handleGenerateVideo}
        disabled={isGenerating}
      >
        {isGenerating ? 'Generating...' : 'Generate Video'}
      </Button>
    </div>
  );

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
            <h3 className="text-base font-medium">Video Generation Settings</h3>
            <ActionButtons />
          </div>

          {isMobile && <MobileVideoPreview />}

          <Accordion title="Core Generation Settings" number="1" defaultOpen={true}>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-sm font-bold text-[#2563EB]">1. Prompt Input</h4>
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
              placeholder="Enter your video prompt here"
              showBatchPrompts={false}
              value={coreSettings.prompt}
              onChange={handlePromptChange}
            />

            <h4 className="mb-2 mt-6 text-sm font-bold text-[#2563EB]">
              2. Video Model Settings
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

export default Txt2VidPage;
