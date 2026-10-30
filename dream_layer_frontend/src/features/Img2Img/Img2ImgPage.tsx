import type { GeneratedImage, GeneratedGrid, CustomWorkflow } from '@/types/api';
import React, { useState, useEffect } from 'react';
import ImageUploader from '@/components/ImageUploader';
import AdvancedSettings from '@/components/AdvancedSettings';
import ExternalExtensions from '@/components/ExternalExtensions';
import CheckpointBrowser from '@/components/checkpoint/CheckpointBrowser';
import LoraBrowser from '@/components/lora/LoraBrowser';
import CustomWorkflowBrowser from '@/components/custom-workflow/CustomWorkflowBrowser';
import PromptInput from '@/components/PromptInput';
import RenderSettings from '@/components/RenderSettings';
import SizingSettings from '@/components/SizingSettings';
import OutputQuantity from '@/components/OutputQuantity';
import GenerationID from '@/components/GenerationID';
import ImagePreview from '@/components/tabs/img2img/ImagePreview';
import { useImg2ImgGalleryStore } from '@/stores/useImg2ImgGalleryStore';
import useLoraStore from '@/stores/useLoraStore';
import useControlNetStore from '@/stores/useControlNetStore';
import { ControlNetRequest } from '@/types/controlnet';
import { prepareControlNetForAPI, validateControlNetConfig } from '@/utils/controlnetUtils';

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "@/components/ui/accordion";
import { Separator } from "@/components/ui/separator";
import { Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Img2ImgPageProps {
  selectedModel: string;
  onTabChange: (tabId: string) => void;
}

const Img2ImgPage: React.FC<Img2ImgPageProps> = ({ selectedModel, onTabChange }) => {
  const [activeSubTab, setActiveSubTab] = useState("generation");
  const [activeImg2ImgTool, setActiveImg2ImgTool] = useState("img2img");
  const [batchCount, setBatchCount] = useState(1);
  const [batchSize, setBatchSize] = useState(1);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  
  // ControlNet configuration will be managed by useControlNetStore
  
  const {
    inputImage,
    setLoading,
    addImages,
    clearImages,
    coreSettings,
    customWorkflow,
    setCustomWorkflow,
    handlePromptChange,
    handleSamplingSettingsChange,
    handleSizeSettingsChange,
    handleBatchSettingsChange,
    handleSeedChange,
    updateCoreSettings,
    loadFromDatabase
  } = useImg2ImgGalleryStore();
  const selectedLora = useLoraStore(state => state.loraConfig);
  const { controlNetConfig, setControlNetConfig } = useControlNetStore();
  
  useEffect(() => {
    setIsLoaded(true);
    console.log("Img2ImgPage component mounted");
    // Load generation history from database
    loadFromDatabase();
  }, [loadFromDatabase]);

  const handleSubTabChange = (tabId: string) => {
    setActiveSubTab(tabId);
  };

  const handleImg2ImgToolChange = (toolId: string) => {
    setActiveImg2ImgTool(toolId);
  };

  const handleLocalBatchSettingsChange = (newBatchSize: number, newBatchCount: number) => {
    setBatchSize(newBatchSize);
    setBatchCount(newBatchCount);
    // Also update the store
    handleBatchSettingsChange(newBatchCount, newBatchSize);
  };

  const handleCopyPrompts = () => {
    const promptTextarea = document.querySelector('textarea[placeholder="Enter your prompt here"]') as HTMLTextAreaElement;
    const negativePromptTextarea = document.querySelector('textarea[placeholder="Enter negative prompt here"]') as HTMLTextAreaElement;
    
    if (promptTextarea && negativePromptTextarea) {
      const combinedText = `Prompt: ${promptTextarea.value}\nNegative Prompt: ${negativePromptTextarea.value}`;
      navigator.clipboard.writeText(combinedText);
    }
  };

  const handleControlNetChange = (config: ControlNetRequest | null) => {
    console.log('ControlNet config changed in img2img:', config);
    // If config is null, it means ControlNet was disabled
    // If config is provided and enabled, use it, otherwise set to null
    setControlNetConfig(config?.enabled ? config : null);
  };

  const handleGenerateImage = async () => {
    if (isGenerating) {
      await fetch('http://localhost:5004/api/img2img/interrupt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      setIsGenerating(false);
      setLoading(false);
      return;
    }

    if (!inputImage) {
      console.error('No input image selected');
      return;
    }

    setIsGenerating(true);
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('image', inputImage.file);


      // Prepare ControlNet data for API
      let preparedControlNet = null;
      if (controlNetConfig && validateControlNetConfig(controlNetConfig)) {
        try {
          preparedControlNet = await prepareControlNetForAPI(controlNetConfig);
          console.log('Prepared ControlNet for API:', preparedControlNet);
        } catch (error) {
          console.error('Error preparing ControlNet for API:', error);
        }
      }

      // Prepare the request data
      const requestData = {
        ...coreSettings,
        model_name: selectedModel,
        custom_workflow: customWorkflow,
        lora: selectedLora,
        // Only include controlnet if it's properly configured
        ...(preparedControlNet && { controlnet: preparedControlNet })
      };

      console.log('Sending img2img request with data:', requestData);
      console.log('ControlNet config being sent:', controlNetConfig);
      console.log('ControlNet config is null?', controlNetConfig === null);
      console.log('ControlNet config is enabled?', controlNetConfig?.enabled);

      // Send the request data as JSON in the body
      const response = await fetch('http://localhost:5004/api/img2img', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('Img2img response:', data);

      if (data.generated_images) {
        console.log('Generated images from response:', data.generated_images);
        
        const testImage = new Image();
        const firstImageUrl = data.generated_images[0].url;
        
        testImage.onload = () => {
          console.log('Test image loaded successfully:', firstImageUrl);
          const images = data.generated_images.map((img: GeneratedImage) => ({
            id: `${Date.now()}-${Math.random()}`,
            url: img.url,
            prompt: requestData.prompt,
            negativePrompt: requestData.negative_prompt,
            timestamp: Date.now(),
            settings: requestData
          }));
          
          console.log('Adding images to store:', images);
          addImages(images);
          setLoading(false);
          setIsGenerating(false);
        };
        
        testImage.onerror = (error) => {
          console.error('Failed to load test image:', error);
          setLoading(false);
          setIsGenerating(false);
          throw new Error('Failed to load generated image');
        };
        
        testImage.src = firstImageUrl;
      } else {
        console.error('No generated_images in response:', data);
        setLoading(false);
        setIsGenerating(false);
        throw new Error('No images were generated');
      }
    } catch (error) {
      console.error('Error in handleGenerateImage:', error);
      setLoading(false);
      setIsGenerating(false);
    }
  };

  const getSectionTitle = () => {
    switch (activeSubTab) {
      case "checkpoints":
        return "Custom Workflow Management";
      case "lora":
        return "LoRA Browser";
      default:
        return "Core Generation Settings";
    }
  };

  // Advanced option handlers
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


  const renderSubTabContent = () => {
    switch (activeSubTab) {
      case "checkpoints":
        return <CustomWorkflowBrowser 
          onWorkflowChange={setCustomWorkflow}
          currentWorkflow={customWorkflow}
        />;
      case "lora":
        return <LoraBrowser />;
      default:
        return (
          <>
            <ImageUploader activeImg2ImgTool={activeImg2ImgTool} />
            
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-sm font-bold text-primary">1. Prompt Input</h4>
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
              value={coreSettings.prompt}
              onChange={(value) => handlePromptChange(value)}
            />
            <PromptInput 
              label="b) Negative Prompt"
              negative={true}
              maxLength={500}
              placeholder="Enter negative prompt here"
              value={coreSettings.negative_prompt}
              onChange={(value) => handlePromptChange(value, true)}
            />
            
            {/* <h4 className="mb-2 mt-6 text-sm font-bold text-[#2563EB]">2. Sampling Settings</h4> */}
            <RenderSettings 
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
              4. Output Quantity: {batchCount * batchSize}
            </h4>
            <OutputQuantity 
              batchCount={batchCount}
              batchSize={batchSize}
              onChange={handleLocalBatchSettingsChange}
            />
            
            <h4 className="mb-2 mt-6 text-sm font-bold text-[#2563EB]">5. Seed Settings</h4>
            <GenerationID 
              seed={coreSettings.seed}
              random={coreSettings.random_seed}
              onChange={handleSeedChange}
            />
          </>
        );
    }
  };

  const Img2ImgToolsNavigation = () => {
    const tools = [
      { id: "img2img", label: "Img2Img", active: activeImg2ImgTool === "img2img" },
      { id: "inpaint", label: "Inpaint", active: activeImg2ImgTool === "inpaint" },
      { id: "outpaint", label: "Inpaint Upload", active: activeImg2ImgTool === "outpaint" }
    ].filter(tool => tool.id !== 'inpaint' && tool.id !== 'outpaint');

    return (
      <div className="mb-4">
        <div data-orientation="horizontal" role="none" className="shrink-0 bg-border h-[1px] w-full mt-2 mb-4"></div>
        <div className="flex items-center gap-4 mb-4">
          <span className="text-sm font-medium text-foreground">Img2Img Tools:</span>
          <div className="flex flex-wrap gap-2">
            {tools.map(tool => (
              <div
                key={tool.id}
                onClick={() => handleImg2ImgToolChange(tool.id)}
                className={cn(
                  "flex items-center gap-2 p-2 rounded-full border transition-colors cursor-pointer",
                  tool.active
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-primary/50"
                )}
              >
                <span className="text-xs cursor-pointer truncate font-medium">
                  {tool.label}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div data-orientation="horizontal" role="none" className="shrink-0 bg-border h-[1px] w-full mb-2"></div>
      </div>
    );
  };

  const SubTabNavigation = ({ tabs, onTabChange }) => {
    return (
      <div className="flex flex-wrap gap-3">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
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

  if (!isLoaded) {
    return (
      <div className="p-8 bg-background text-foreground border border-border rounded-md">
        <p>Loading Img2Img interface...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      <div className="flex-1 space-y-4">
        <div className="flex flex-col">
          <div className="mb-[18px] flex flex-col space-y-2 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
            <h3 className="text-base font-medium text-foreground">Image to Image Generation</h3>
            <div className="flex space-x-2">
              <Button 
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                onClick={handleGenerateImage}
                disabled={!inputImage}
              >
                {isGenerating ? 'Interrupt' : 'Generate Image'}
              </Button>
              
            </div>
          </div>
          
          <div className="mb-[18px]">
            <SubTabNavigation 
              tabs={[
                { id: "generation", label: "Generation", active: activeSubTab === "generation" },
                { id: "checkpoints", label: "Custom Workflow", active: activeSubTab === "checkpoints" },
                { id: "lora", label: "LoRA", active: activeSubTab === "lora" }
              ]}
              onTabChange={handleSubTabChange}
            />
          </div>
          
          {activeSubTab !== "checkpoints" && activeSubTab !== "lora" && (
            <Img2ImgToolsNavigation />
          )}
          
          <Accordion type="multiple" defaultValue={["section-1"]} className="space-y-4">
            <AccordionItem value="section-1" className="border border-border rounded-md overflow-hidden bg-card">
              <AccordionTrigger className="px-4 py-3 font-medium bg-card hover:bg-accent">
                <span className="flex items-center text-foreground">
                  <span className="mr-2 text-foreground">1.</span>
                  {getSectionTitle()}
                </span>
              </AccordionTrigger>
              <AccordionContent className="px-4 py-3 bg-card">
                {renderSubTabContent()}
              </AccordionContent>
            </AccordionItem>
            
            {activeSubTab !== "checkpoints" && activeSubTab !== "lora" && (
              <AccordionItem value="section-2" className="border border-border rounded-md overflow-hidden bg-card">
                <AccordionTrigger className="px-4 py-3 font-medium bg-card hover:bg-accent">
                  <span className="flex items-center text-foreground">
                    <span className="mr-2 text-foreground">2.</span>
                    Advanced Optional Settings
                  </span>
                </AccordionTrigger>
                <AccordionContent className="px-4 py-3 bg-card">
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
                </AccordionContent>
              </AccordionItem>
            )}
            
            {activeSubTab !== "checkpoints" && activeSubTab !== "lora" && (
              <AccordionItem value="section-3" className="border border-border rounded-md overflow-hidden bg-card">
                <AccordionTrigger className="px-4 py-3 font-medium bg-card hover:bg-accent">
                  <span className="flex items-center text-foreground">
                    <span className="mr-2 text-foreground">3.</span>
                    External Extensions & Add-ons
                  </span>
                </AccordionTrigger>
                <AccordionContent className="px-4 py-3 bg-card">
                  <ExternalExtensions 
                    isImg2ImgTab={true}
                    onControlNetChange={handleControlNetChange}
                  />
                </AccordionContent>
              </AccordionItem>
            )}
          </Accordion>
        </div>
      </div>
      <div className="w-full lg:w-[512px] space-y-4">
        <ImagePreview onTabChange={onTabChange} />
      </div>
    </div>
  );
};

export default Img2ImgPage;