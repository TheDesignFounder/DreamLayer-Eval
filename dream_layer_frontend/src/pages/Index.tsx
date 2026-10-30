import React, { useState, useEffect } from 'react';
import NavBar from '@/components/NavBar';
import ModelSelector from '@/components/ModelSelector';
import TabsNav from '@/components/Navigation/TabsNav';
import { Txt2ImgPage } from '@/features/Txt2Img';
import { Img2ImgPage } from '@/features/Img2Img';
import { Txt2VidPage } from '@/features/Txt2Vid';
import { Img2VidPage } from '@/features/Img2Vid';
import { Img2TxtPage } from '@/features/Img2Txt';
import ExtrasPage from '@/features/Extras';
import { ModelManagerPage } from '@/features/ModelManager';
import { PNGInfoPage } from '@/features/PNGInfo';
import { ConfigurationsPage } from '@/features/Configurations';
import { RunRegistryPage } from '@/features/RunRegistry';
import { ReportBundlePage } from '@/features/ReportBundle';
import { useTxt2ImgGalleryStore } from '@/stores/useTxt2ImgGalleryStore';
import { useImg2ImgGalleryStore } from '@/stores/useImg2ImgGalleryStore';

const Index = () => {
  const [activeTab, setActiveTab] = useState(() => {
    // Check if there's a saved tab from refresh
    const savedTab = localStorage.getItem('activeTab');
    if (savedTab) {
      localStorage.removeItem('activeTab');
      return savedTab;
    }
    return "txt2img";
  });
  const [selectedModel, setSelectedModel] = useState<string>("v1-5-pruned-emaonly-fp16.safetensors");

  const handleTabChange = (tabId: string) => {
    // Don't clear images when switching tabs - they persist via database
    setActiveTab(tabId);
  };

  const handleModelSelect = (modelName: string, modelType: 'image' | 'video' | 'text') => {
    setSelectedModel(modelName);

    // Auto-switch to appropriate tab based on model type if needed
    const isImageTab = activeTab === 'txt2img' || activeTab === 'img2img';
    const isVideoTab = activeTab === 'txt2vid' || activeTab === 'img2vid';

    // If video model selected but on image tab, switch to txt2vid
    if (modelType === 'video' && isImageTab) {
      setActiveTab('txt2vid');
    }
    // If image model selected but on video tab, switch to txt2img
    else if (modelType === 'image' && isVideoTab) {
      setActiveTab('txt2img');
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case "txt2img":
        return <Txt2ImgPage selectedModel={selectedModel} onTabChange={handleTabChange} />;
      case "img2img":
        return <Img2ImgPage selectedModel={selectedModel} onTabChange={handleTabChange} />;
      case "txt2vid":
        return <Txt2VidPage selectedModel={selectedModel} onTabChange={handleTabChange} />;
      case "img2vid":
        return <Img2VidPage selectedModel={selectedModel} onTabChange={handleTabChange} />;
      case "img2txt":
        return <Img2TxtPage onTabChange={handleTabChange} />;
      case "extras":
        return <ExtrasPage />;
      case "models":
        return <ModelManagerPage />;
      case "pnginfo":
        return <PNGInfoPage />;
      case "configurations":
        return <ConfigurationsPage />;
      case "runregistry":
        return <RunRegistryPage />;
      case "reportbundle":
        return <ReportBundlePage />;
      default:
        return <Txt2ImgPage selectedModel={selectedModel} onTabChange={handleTabChange} />;
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <NavBar />
      <a href="/research" className="mx-auto mt-3 rounded border px-4 py-2">Open research workbench</a>
      <div className="container mx-auto max-w-7xl px-4 py-6">
        <ModelSelector onModelSelect={handleModelSelect} currentTab={activeTab} />
        <h2 className="mb-2 mt-6 text-lg font-medium text-foreground">Generation Modules</h2>
        <div className="bg-card rounded-lg shadow-[0px_4px_24px_rgba(51,51,51,0.15)] p-6 border border-border">
          <TabsNav activeTab={activeTab} onTabChange={handleTabChange} />
          {renderTabContent()}
        </div>
      </div>
    </div>
  );
};

export default Index;
