import React, { useState, useEffect } from 'react';
import Accordion from '@/components/Accordion';
import PromptInput from '@/components/PromptInput';
import RenderSettings from '@/components/RenderSettings';
import SizingSettings from '@/components/SizingSettings';
import OutputQuantity from '@/components/OutputQuantity';
import GenerationID from '@/components/GenerationID';
import AdvancedSettings from '@/components/AdvancedSettings';
import ExternalExtensions from '@/components/ExternalExtensions';
import ImagePreview from '@/components/tabs/txt2img/ImagePreview';
import CheckpointBrowser from '@/components/checkpoint/CheckpointBrowser';
import LoraBrowser from '@/components/lora/LoraBrowser';
import CustomWorkflowBrowser from '@/components/custom-workflow/CustomWorkflowBrowser';
import { useIsMobile } from '@/hooks/use-mobile';
import { useToast } from '@/hooks/use-toast';
import { Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useTxt2ImgGalleryStore } from '@/stores/useTxt2ImgGalleryStore';
import { Txt2ImgCoreSettings, defaultTxt2ImgSettings } from '@/types/generationSettings';
import useControlNetStore from '@/stores/useControlNetStore';
import { ControlNetRequest } from '@/types/controlnet';
import useLoraStore from '@/stores/useLoraStore';
import { LoraRequest } from '@/types/lora';
import { io, Socket } from 'socket.io-client';

interface Txt2ImgPageProps {
  selectedModel: string;
  onTabChange: (tabId: string) => void;
}

const Txt2ImgPage: React.FC<Txt2ImgPageProps> = ({ selectedModel, onTabChange }) => {
  const [activeSubTab, setActiveSubTab] = useState("generation");
  const [coreSettings, setCoreSettings] = useState<Txt2ImgCoreSettings>({
    ...defaultTxt2ImgSettings,
    model_name: selectedModel
  });
  const [customWorkflow, setCustomWorkflow] = useState<any | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [batchPrompts, setBatchPrompts] = useState<string[]>([]);
  const [progress, setProgress] = useState({ current: 0, total: 0, currentPrompt: '' });
  const [socket, setSocket] = useState<Socket | null>(null);
  const [grids, setGrids] = useState<any[]>([]);
  const [isCreatingGrid, setIsCreatingGrid] = useState(false);
  const isMobile = useIsMobile();
  const { toast } = useToast();
  const addImages = useTxt2ImgGalleryStore(state => state.addImages);
  const setLoading = useTxt2ImgGalleryStore(state => state.setLoading);
  const loadFromDatabase = useTxt2ImgGalleryStore(state => state.loadFromDatabase);
  const controlNetConfig = useControlNetStore(state => state.controlNetConfig);
  const { setControlNetConfig } = useControlNetStore();
  const loraConfig = useLoraStore(state => state.loraConfig);

  // Add effect to update model when selectedModel prop changes
  useEffect(() => {
    updateCoreSettings({ model_name: selectedModel });
  }, [selectedModel]);

  // Load generation history from database on mount
  useEffect(() => {
    loadFromDatabase();
  }, [loadFromDatabase]);

  // Check for prompt from session storage (from img2txt "Send to" button)
  useEffect(() => {
    const storedPrompt = window.sessionStorage.getItem('txt2imgPrompt');
    if (storedPrompt) {
      updateCoreSettings({ prompt: storedPrompt });
      window.sessionStorage.removeItem('txt2imgPrompt');
    }
  }, []);

  const updateCoreSettings = (updates: Partial<Txt2ImgCoreSettings>) => {
    setCoreSettings(prev => ({ ...prev, ...updates }));
  };

  const handlePromptChange = (value: string, isNegative: boolean = false) => {
    updateCoreSettings(isNegative ? { negative_prompt: value } : { prompt: value });
  };

  const handleBatchSettingsChange = (batchSize: number, batchCount: number) => {
    updateCoreSettings({ batch_size: batchSize, batch_count: batchCount });
  };
  const handleGenerateReport = async () => {
  try {
    const response = await fetch("/api/generate-report", { method: "POST" });
    if (!response.ok) throw new Error("Failed to generate report");
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "report.zip"; 
    link.click();
  } catch (error) {
    console.error("Error generating report:", error);
  }
};


  const handleSamplingSettingsChange = (sampler: string, scheduler: string, steps: number, cfg: number) => {
    updateCoreSettings({
      sampler_name: sampler,
      scheduler: scheduler,
      steps: steps,
      cfg_scale: cfg
    });
  };

  const handleSizeSettingsChange = (width: number, height: number) => {
    updateCoreSettings({ width, height });
  };

  const handleSeedChange = (seed: number, random: boolean = true) => {
    updateCoreSettings({ seed, random_seed: random });
  };

  const handleSubTabChange = (tabId: string) => {
    setActiveSubTab(tabId);
  };

  const handleControlNetChange = (config: ControlNetRequest | null) => {
    console.log('ControlNet config changed in txt2img:', config);
    // If config is null, it means ControlNet was disabled
    setControlNetConfig(config?.enabled ? config : null);
  };

  const handleRestoreFacesChange = (enabled: boolean) => {
    updateCoreSettings({ restore_faces: enabled });
  };

  const handleFaceRestorationModelChange = (model: string) => {
    updateCoreSettings({ face_restoration_model: model });
  };

  const handleCodeformerWeightChange = (weight: number) => {
    updateCoreSettings({ codeformer_weight: weight });
  };

  const handleGfpganWeightChange = (weight: number) => {
    updateCoreSettings({ gfpgan_weight: weight });
  };

  const handleTilingChange = (enabled: boolean) => {
    updateCoreSettings({ tiling: enabled });
  };

  const handleTileSizeChange = (size: number) => {
    updateCoreSettings({ tile_size: size });
  };

  const handleTileOverlapChange = (overlap: number) => {
    updateCoreSettings({ tile_overlap: overlap });
  };

  const handleHiresFixChange = (enabled: boolean) => {
    updateCoreSettings({ hires_fix: enabled });
  };

  const handleRefinerEnabledChange = (enabled: boolean) => {
    updateCoreSettings({ refiner_enabled: enabled });
  };

  const handleRefinerModelChange = (model: string) => {
    updateCoreSettings({ refiner_model: model });
  };

  const handleRefinerSwitchAtChange = (value: number) => {
    updateCoreSettings({ refiner_switch_at: value });
  };

  const handleCopyPrompts = () => {
    const promptTextarea = document.querySelector('textarea[placeholder="Enter your prompt here"]') as HTMLTextAreaElement;
    const negativePromptTextarea = document.querySelector('textarea[placeholder="Enter negative prompt here"]') as HTMLTextAreaElement;
    
    if (promptTextarea && negativePromptTextarea) {
      const combinedText = `Prompt: ${promptTextarea.value}\nNegative Prompt: ${negativePromptTextarea.value}`;
      navigator.clipboard.writeText(combinedText);
    }
  };

  const handleGenerateImage = async () => {
    // Handle interrupt if already generating
    if (isGenerating) {
      await fetch('http://localhost:5001/api/txt2img/interrupt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      setIsGenerating(false);
      setLoading(false);
      return;
    }

    // === GUARD: Ensure ControlNet image is set ===
    // if (controlNetConfig?.enabled) {
    //   const missingImage = controlNetConfig.units.some(unit => unit.enabled && !unit.input_image);
    //   if (missingImage) {
    //     alert("Please upload a ControlNet image for all enabled units before generating.");
    //     setIsGenerating(false);
    //     setLoading(false);
    //     return;
    //   }
    // }
    // === END GUARD ===

    try {
      setIsGenerating(true);
      setLoading(true);
      
      console.log("ControlNetConfig at generate time:", JSON.stringify(controlNetConfig, null, 2));
      
      // Prepare the request data
      const requestData = {
        ...coreSettings,
        custom_workflow: customWorkflow, // Add the custom workflow to the request
        // Only include controlnet if it's properly configured
        ...(controlNetConfig && { controlnet: controlNetConfig }),
        // Only include lora if it's enabled and configured
        ...(loraConfig?.enabled && { lora: loraConfig })
      };
      
      if (controlNetConfig?.units) {
        console.log('📦 ControlNet Units Details:');
        controlNetConfig.units.forEach((unit, index) => {
          if (unit.input_image) {
            console.log(`    Input image preview: ${unit.input_image.substring(0, 100)}...`);
          }
        });
      }
      console.log('ControlNet config being sent:', JSON.stringify(controlNetConfig, null, 2));
      const response = await fetch('http://localhost:5001/api/txt2img', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      console.log('Response status:', response.status);
      console.log('Response headers:', response.headers);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Error response:', errorText);
        throw new Error(`Failed to generate image: ${errorText}`);
      }

      const data = await response.json();
      console.log('Response data:', data);

      if (data.generated_images) {
        const images = data.generated_images.map((img: any) => {
          // Use the URL directly from the response
          const imageUrl = img.url;
          
          // Create a test image to verify the URL works
          const testImage = new Image();
          testImage.src = imageUrl;
          
          // Log the URL and loading status
          console.log('Testing image URL:', imageUrl);
          testImage.onload = () => console.log('Image loaded successfully:', imageUrl);
          testImage.onerror = (e) => console.error('Image failed to load:', imageUrl, e);
          
          return {
            id: `${Date.now()}-${Math.random()}`,
            url: imageUrl,
            prompt: coreSettings.prompt,
            negativePrompt: coreSettings.negative_prompt,
            timestamp: Date.now(),
            settings: {
              ...coreSettings
            }
          };
        });
        
        console.log('Adding images to gallery:', images);
        addImages(images);
      } else {
        console.error('No generated_images in response:', data);
        throw new Error('No images were generated');
      }
    } catch (error) {
      console.error('Error details:', error);
    } finally {
      setLoading(false);
      setIsGenerating(false);
    }
  };

  const handleBatchPrompts = async (prompts: string[]) => {
    if (isGenerating) return;
    
    try {
      setIsGenerating(true);
      setLoading(true);
      setProgress({ current: 0, total: prompts.length, currentPrompt: '' });
      
      // Connect to WebSocket
      const newSocket = io('http://localhost:5001');
      setSocket(newSocket);
      
      // Listen for progress updates
      newSocket.on('progress', (data) => {
        if (data.type === 'progress') {
          setProgress({
            current: data.current,
            total: data.total,
            currentPrompt: data.current_prompt
          });
        } else if (data.type === 'batch_complete') {
          toast({
            title: "Batch complete",
            description: `Generated ${data.processed_prompts} of ${data.total_prompts} images`
          });
        } else if (data.type === 'error') {
          toast({
            title: "Prompt failed",
            description: `Failed: ${data.current_prompt?.substring(0, 50)}...`,
            variant: "destructive"
          });
        }
      });
      
      // Listen for real-time image generation
      newSocket.on('image_generated', (data) => {
        const newImage = {
          id: `${Date.now()}-${Math.random()}`,
          url: data.image_data.url,
          prompt: data.prompt,
          negativePrompt: coreSettings.negative_prompt,
          timestamp: Date.now(),
          settings: { ...coreSettings }
        };
        addImages([newImage]);
      });
      
      const requestData = {
        ...coreSettings,
        prompts,
        custom_workflow: customWorkflow,
        ...(controlNetConfig && { controlnet: controlNetConfig }),
        ...(loraConfig?.enabled && { lora: loraConfig })
      };
      
      const response = await fetch('http://localhost:5001/api/txt2img/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData),
      });

      if (!response.ok) {
        throw new Error(`Failed to process batch: ${await response.text()}`);
      }

      const data = await response.json();
      
      // Remove the batch completion image adding since images are now added in real-time
      // if (data.all_images?.length > 0) {
      //   const images = data.all_images.map((img: any) => ({
      //     id: `${Date.now()}-${Math.random()}`,
      //     url: img.url,
      //     prompt: img.prompt || "Batch generated",
      //     negativePrompt: coreSettings.negative_prompt,
      //     timestamp: Date.now(),
      //     settings: { ...coreSettings }
      //   }));
      //   
      //   addImages(images);
      // }
    } catch (error) {
      toast({
        title: "Batch failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
      setIsGenerating(false);
      setProgress({ current: 0, total: 0, currentPrompt: '' });
      if (socket) {
        socket.disconnect();
        setSocket(null);
      }
    }
  };

  const handleBatchPromptsLoaded = (prompts: string[]) => {
    setBatchPrompts(prompts);
  };

  const handleGenerateWithBatch = () => {
    if (batchPrompts.length > 0) {
      handleBatchPrompts(batchPrompts);
      setBatchPrompts([]); // Clear after starting generation
    } else {
      handleGenerateImage();
    }
  };

  const handleCreateGrid = async () => {
    setIsCreatingGrid(true);
    try {
      const response = await fetch('http://localhost:5001/api/txt2img/create-grid', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          batch_size: coreSettings.batch_size,
          batch_count: coreSettings.batch_count
        })
      });
      const result = await response.json();
      if (result.status === 'success') {
        setGrids(prev => [...prev, ...result.grids]);
        toast({
          title: "Success",
          description: `Created ${result.grids.length} grids successfully!`,
        });
      } else {
        toast({
          title: "Error",
          description: result.message || 'Failed to create grids',
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: 'Failed to create grids',
        variant: "destructive",
      });
    } finally {
      setIsCreatingGrid(false);
    }
  };

  const getAccordionTitle = () => {
    switch (activeSubTab) {
      case "checkpoints":
        return "Custom Workflow Management";
      case "lora":
        return "LoRA Browser";
      default:
        return "Core Generation Settings";
    }
  };

  const ActionButtons = () => (
    <div className="flex space-x-2">
      <Button 
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        onClick={handleGenerateWithBatch}
        disabled={false}
      >
        {isGenerating ? 'Interrupt' : batchPrompts.length > 0 ? `Generate Batch (${batchPrompts.length})` : 'Generate Image'}
      </Button>
      <Button 
        onClick={handleCreateGrid}
        disabled={isCreatingGrid}
        variant="outline"
        className="whitespace-nowrap"
      >
        {isCreatingGrid ? 'Creating Grids...' : 'Create Grid'}
      </Button>
      {false && <button className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground">
        Save Settings
      </button>}
    </div>
  );

  const MobileImagePreview = () => (
    <div className="my-4 w-full">
      <ImagePreview onTabChange={onTabChange} grids={grids} />
    </div>
  );

  const SubTabNavigation = () => {
    const tabs = [
      { id: "generation", label: "Generation", active: activeSubTab === "generation" },
      { id: "checkpoints", label: "Custom Workflow", active: activeSubTab === "checkpoints" },
      { id: "lora", label: "Lora", active: activeSubTab === "lora" }
    ];

    return (
      <div className="flex flex-wrap gap-3">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => handleSubTabChange(tab.id)}
            className={cn(
              "px-6 py-2.5 rounded-full text-sm font-medium transition-all duration-200 border focus:outline-none focus:ring-2 focus:ring-offset-2",
              tab.active
                ? "bg-blue-600 text-white shadow-md hover:bg-blue-700 focus:ring-blue-500 border-blue-600"
                : "bg-transparent text-gray-600 hover:bg-gray-50 border-gray-200 hover:border-gray-300 dark:text-gray-400 dark:border-gray-600 dark:hover:bg-gray-800/50 dark:hover:border-gray-500"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
    );
  };

  const renderActiveSubTabContent = () => {
    switch (activeSubTab) {
      case "checkpoints":
        return <CustomWorkflowBrowser 
          onWorkflowChange={setCustomWorkflow}
          currentWorkflow={customWorkflow}
        />;
      case "lora":
        return <LoraBrowser />;
      default:
        // "generation" tab (default)
        return (
          <>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-sm font-bold text-[#2563EB]">1. Prompt Input</h4>
              <Button 
                onClick={handleCopyPrompts}
                variant="outline"
                size="sm"
                className="text-xs px-2 py-1 h-auto flex items-center gap-1"
              >
                <Copy className="h-3.5 w-3.5" />
                Copy Prompts
              </Button>
            </div>
            <PromptInput 
              label="a) Prompt"
              maxLength={500}
              placeholder="Enter your prompt here"
              showBatchPrompts={true}
              value={coreSettings.prompt}
              onChange={(value) => handlePromptChange(value)}
              onBatchPromptsLoaded={handleBatchPromptsLoaded}
            />
            {batchPrompts.length > 0 && (
              <div className="text-sm text-muted-foreground bg-muted p-2 rounded">
                <strong>Batch loaded:</strong> {batchPrompts.length} prompts ready
                <div className="text-xs mt-1">Preview: {batchPrompts.slice(0, 3).join(', ')}{batchPrompts.length > 3 ? '...' : ''}</div>
              </div>
            )}
            {progress.total > 0 && (
              <div className="text-sm text-muted-foreground bg-blue-50 p-2 rounded">
                <strong>Processing {progress.current} of {progress.total}:</strong> {progress.currentPrompt}
              </div>
            )}
            <PromptInput 
              label="b) Negative Prompt"
              negative={true}
              maxLength={500}
              placeholder="Enter negative prompt here"
              value={coreSettings.negative_prompt}
              onChange={(value) => handlePromptChange(value, true)}
            />
            
            <RenderSettings 
              showResizeMode={false}
              sampler={coreSettings.sampler_name}
              scheduler={coreSettings.scheduler}
              steps={coreSettings.steps}
              cfg={coreSettings.cfg_scale}
              onChange={handleSamplingSettingsChange}
            />
            
            <h4 className="mb-2 mt-6 text-sm font-bold text-[#2563EB]">3. Sizing</h4>
            <SizingSettings 
              width={coreSettings.width}
              height={coreSettings.height}
              onChange={handleSizeSettingsChange}
            />
            
            <h4 className="mb-2 mt-6 text-sm font-bold text-[#2563EB]">
              4. Output Quantity: {coreSettings.batch_count * coreSettings.batch_size}
            </h4>
            <OutputQuantity 
              batchCount={coreSettings.batch_count}
              batchSize={coreSettings.batch_size}
              onChange={handleBatchSettingsChange}
            />
            
            <div className="flex items-center justify-between mt-6 mb-2">
              <h4 className="text-sm font-bold text-[#2563EB]">5. Seed</h4>
              <div className="flex space-x-2">
                <button 
                  className="text-xs rounded-md border border-input bg-background px-2 py-1 hover:bg-accent hover:text-accent-foreground"
                  onClick={() => handleSeedChange(Math.floor(Math.random() * 1073741824), false)}
                >
                  Randomize Seed
                </button>
                <button 
                  className="text-xs rounded-md border border-input bg-background px-2 py-1 hover:bg-accent hover:text-accent-foreground"
                  onClick={() => handleSeedChange(coreSettings.seed, false)}
                >
                  Reuse Past Seed
                </button>
              </div>
            </div>
            <GenerationID 
              seed={coreSettings.seed}
              random={coreSettings.random_seed}
              onChange={handleSeedChange}
            />
          </>
        );
    }
  };

  return (
    
    <div className={`mb-4 ${isMobile ? 'grid grid-cols-1' : 'grid gap-6 md:grid-cols-[1.8fr_1fr]'}`}>
      {/* Left Column - Controls */}
      <div className="space-y-4">
        <div className="flex flex-col">
          <div className="mb-[18px] flex flex-col space-y-2 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
            <h3 className="text-base font-medium">Generation Settings</h3>
            <ActionButtons />
             <Button
      onClick={handleGenerateReport}
      variant="secondary"
      disabled={isGenerating}
    >
      Generate Report
    </Button>
          </div>
          
          {isMobile && <MobileImagePreview />}
          
          <div className="mb-[18px]">
            <SubTabNavigation />
          </div>
          
          <Accordion title={getAccordionTitle()} number="1" defaultOpen={true}>
            {renderActiveSubTabContent()}
          </Accordion>
          
          {activeSubTab === "generation" && (
            <>
              <Accordion title="Advanced Optional Settings" number="2">
                <AdvancedSettings 
                  restoreFaces={coreSettings.restore_faces}
                  onRestoreFacesChange={handleRestoreFacesChange}
                  faceRestorationModel={coreSettings.face_restoration_model}
                  onFaceRestorationModelChange={handleFaceRestorationModelChange}
                  codeformerWeight={coreSettings.codeformer_weight}
                  onCodeformerWeightChange={handleCodeformerWeightChange}
                  gfpganWeight={coreSettings.gfpgan_weight}
                  onGfpganWeightChange={handleGfpganWeightChange}
                  tiling={coreSettings.tiling}
                  onTilingChange={handleTilingChange}
                  tileSize={coreSettings.tile_size}
                  onTileSizeChange={handleTileSizeChange}
                  overlap={coreSettings.tile_overlap}
                  onOverlapChange={handleTileOverlapChange}
                  hiresFix={coreSettings.hires_fix}
                  onHiresFixChange={handleHiresFixChange}
                  refinerEnabled={coreSettings.refiner_enabled}
                  onRefinerEnabledChange={handleRefinerEnabledChange}
                  refinerModel={coreSettings.refiner_model}
                  onRefinerModelChange={handleRefinerModelChange}
                  refinerSwitchAt={coreSettings.refiner_switch_at}
                  onRefinerSwitchAtChange={handleRefinerSwitchAtChange}
                />
              </Accordion>
              
              <Accordion title="External Extensions & Add-ons" number="3">
                <ExternalExtensions 
                  isImg2ImgTab={false} 
                  onControlNetChange={handleControlNetChange}
                />
              </Accordion>
            </>
          )}
        </div>
      </div>
      
      {/* Right Column - Preview */}
      {!isMobile && (
        <div>
          <ImagePreview onTabChange={onTabChange} grids={grids} />
        </div>
      )}
    </div>
  );
};

export default Txt2ImgPage;
