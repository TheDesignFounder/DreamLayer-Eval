
import React, { useState } from 'react';
import Accordion from '@/components/Accordion';
import Slider from '@/components/Slider';
import SubTabNavigation from '@/components/SubTabNavigation';

const ExtrasTab = () => {
  const [activeSubTab, setActiveSubTab] = useState("upscale");
  
  // Grid export state
  const [isCreatingGrid, setIsCreatingGrid] = useState(false);
  const [gridResult, setGridResult] = useState(null);
  const [gridError, setGridError] = useState(null);
  const [gridSettings, setGridSettings] = useState({
    count: '4',
    gridSize: '2x2',
    showLabels: true,
    showFilenames: false,
    filename: 'labeled_grid_export.png'
  });
  
  const subtabs = [
    { id: "upscale", label: "Upscale", active: activeSubTab === "upscale" },
    { id: "process", label: "Post-processing", active: activeSubTab === "process" },
    { id: "batch", label: "Batch Process", active: activeSubTab === "batch" },
    { id: "grid", label: "Grid Export", active: activeSubTab === "grid" },
  ];
  
  // Debug logs to verify component is loading with our changes
  console.log("🔥 ExtrasTab loaded with Grid Export feature - UPDATED VERSION");
  console.log("🔥 Current subtabs count:", subtabs?.length || 0);
  console.log("🔥 Subtabs:", subtabs.map(tab => tab.label));

  const handleSubTabChange = (tabId: string) => {
    setActiveSubTab(tabId);
  };

  const handleCreateGrid = async () => {
    setIsCreatingGrid(true);
    setGridError(null);
    setGridResult(null);

    try {
      const response = await fetch('http://localhost:5003/api/extras/grid-export', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          count: parseInt(gridSettings.count),
          grid_size: gridSettings.gridSize === 'auto' ? 'auto' : gridSettings.gridSize,
          filename: gridSettings.filename,
          show_labels: gridSettings.showLabels,
          show_filenames: gridSettings.showFilenames
        })
      });

      const result = await response.json();
      
      if (result.status === 'success') {
        setGridResult(result.data);
      } else {
        setGridError(result.message || 'Failed to create grid');
      }
    } catch (error) {
      setGridError('Network error: Unable to connect to backend service');
      console.error('Grid creation error:', error);
    } finally {
      setIsCreatingGrid(false);
    }
  };

  const handleGridSettingChange = (key: string, value: unknown) => {
    setGridSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };
  
  const renderSubTabContent = () => {
    switch (activeSubTab) {
      case "grid":
        return (
          <div className="space-y-4 mb-4">
            <div className="mb-4">
              <label htmlFor="gridCount" className="mb-1 block text-sm">Number of Images:</label>
              <select 
                id="gridCount" 
                value={gridSettings.count}
                onChange={(e) => handleGridSettingChange('count', e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="4">4 Recent Images</option>
                <option value="6">6 Recent Images</option>
                <option value="8">8 Recent Images</option>
                <option value="9">9 Recent Images</option>
                <option value="12">12 Recent Images</option>
                <option value="16">16 Recent Images</option>
              </select>
            </div>
            
            <div className="mb-4">
              <label htmlFor="gridSize" className="mb-1 block text-sm">Grid Layout:</label>
              <select 
                id="gridSize" 
                value={gridSettings.gridSize}
                onChange={(e) => handleGridSettingChange('gridSize', e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="2x2">2x2 Grid</option>
                <option value="2x3">2x3 Grid</option>
                <option value="3x3">3x3 Grid</option>
                <option value="4x2">4x2 Grid</option>
                <option value="4x3">4x3 Grid</option>
                <option value="4x4">4x4 Grid</option>
                <option value="auto">Auto Layout</option>
              </select>
            </div>
            
            <div className="flex items-center mb-4">
              <input 
                type="checkbox" 
                id="showLabels" 
                checked={gridSettings.showLabels}
                onChange={(e) => handleGridSettingChange('showLabels', e.target.checked)}
                className="mr-2"
              />
              <label htmlFor="showLabels" className="text-sm">Show Parameter Labels</label>
            </div>
            
            <div className="flex items-center mb-4">
              <input 
                type="checkbox" 
                id="showFilenames" 
                checked={gridSettings.showFilenames}
                onChange={(e) => handleGridSettingChange('showFilenames', e.target.checked)}
                className="mr-2"
              />
              <label htmlFor="showFilenames" className="text-sm">Include Filenames</label>
            </div>
            
            <div className="mb-4">
              <label htmlFor="gridFilename" className="mb-1 block text-sm">Output Filename:</label>
              <input
                id="gridFilename"
                type="text"
                value={gridSettings.filename}
                onChange={(e) => handleGridSettingChange('filename', e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="labeled_grid_export.png"
              />
            </div>
          </div>
        );
      case "process":
        return (
          <div className="space-y-4 mb-4">
            <div className="mb-4">
              <label htmlFor="processor" className="mb-1 block text-sm">Processing Type:</label>
              <select id="processor" className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                <option value="fix_face">Fix Faces</option>
                <option value="colorize">Colorize</option>
                <option value="remove_bg">Remove Background</option>
                <option value="enhance">Image Enhancement</option>
              </select>
            </div>
            
            <Slider
              min={0}
              max={100}
              defaultValue={75}
              label="Effect Strength"
            />
            
            <div className="flex items-center mb-4">
              <input type="checkbox" id="preserveColors" className="mr-2"/>
              <label htmlFor="preserveColors" className="text-sm">Preserve Original Colors</label>
            </div>
          </div>
        );
      case "batch":
        return (
          <div className="space-y-4 mb-4">
            <div className="mb-4 p-4 border-2 border-dashed border-border rounded-md text-center">
              <p className="text-muted-foreground mb-2">Drop multiple images here or click to browse</p>
              <button className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground">
                Browse Files
              </button>
            </div>
            
            <div className="mb-4">
              <label htmlFor="batchOperation" className="mb-1 block text-sm">Batch Operation:</label>
              <select id="batchOperation" className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                <option value="resize">Resize All</option>
                <option value="upscale">Upscale All</option>
                <option value="convert">Convert Format</option>
                <option value="enhance">Enhance All</option>
              </select>
            </div>
            
            <div className="mb-4">
              <label htmlFor="outputDir" className="mb-1 block text-sm">Output Directory:</label>
              <input
                id="outputDir"
                type="text"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="/output/batch_processed/"
              />
            </div>
          </div>
        );
      default:
        // "upscale" tab (default)
        return (
          <div className="space-y-4 mb-4">
            <div className="mb-4">
              <label htmlFor="upscaler" className="mb-1 block text-sm">Upscaler Model:</label>
              <select id="upscaler" className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                <option value="esrgan">ESRGAN 4x</option>
                <option value="swinir">SwinIR 4x</option>
                <option value="real-esrgan">Real-ESRGAN 4x+</option>
                <option value="sd-upscaler">SD Upscaler</option>
              </select>
            </div>
            
            <Slider
              min={1}
              max={8}
              defaultValue={2}
              label="Upscale Factor"
            />
            
            <Slider
              min={0}
              max={100}
              defaultValue={50}
              label="Denoising Strength"
              sublabel="| Lower values preserve more details"
            />
            
            <div className="flex items-center mb-4">
              <input type="checkbox" id="faceRestoration" className="mr-2"/>
              <label htmlFor="faceRestoration" className="text-sm">Apply Face Restoration</label>
            </div>
            
            <div className="flex items-center">
              <input type="checkbox" id="colorCorrection" className="mr-2"/>
              <label htmlFor="colorCorrection" className="text-sm">Apply Color Correction</label>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="mb-4 grid gap-6 md:grid-cols-[2fr_1fr]">
      {/* Left Column - Controls */}
      <div className="space-y-4">
        <div className="flex flex-col">
          <div className="mb-[18px] flex flex-col space-y-2 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
            <h3 className="text-base font-medium">
              {activeSubTab === "grid" ? "Grid Export" : "Image Post-Processing"}
            </h3>
            <div className="flex space-x-2">
              <button 
                onClick={activeSubTab === "grid" ? handleCreateGrid : undefined}
                disabled={activeSubTab === "grid" && isCreatingGrid}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {activeSubTab === "grid" ? (isCreatingGrid ? "Creating Grid..." : "Create Grid") : "Process Image"}
              </button>
              <button className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground">
                Save Settings
              </button>
            </div>
          </div>
          
          <SubTabNavigation 
            className="mb-[18px]"
            tabs={subtabs} 
            onTabChange={handleSubTabChange}
          />
          
          <Accordion title={activeSubTab === "grid" ? "Recent Images" : "Input Image"} number="1" defaultOpen={true}>
            {activeSubTab === "grid" ? (
              <div className="mb-4 p-4 border border-border rounded-md">
                <p className="text-muted-foreground mb-2">Grid will be created from most recent generated images</p>
                <div className="text-sm text-muted-foreground">
                  <p>• Images will be automatically selected based on creation time</p>
                  <p>• Generation parameters will be extracted from logs</p>
                  <p>• Grid layout will be optimized for the selected count</p>
                </div>
              </div>
            ) : (
              <div className="mb-4 p-4 border-2 border-dashed border-border rounded-md text-center">
                <p className="text-muted-foreground mb-2">Drag & drop an image here or click to browse</p>
                <button className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground">
                  Browse Files
                </button>
              </div>
            )}
          </Accordion>
          
          <Accordion title={activeSubTab === "upscale" ? "Upscaling Options" : 
                      activeSubTab === "process" ? "Processing Options" : 
                      activeSubTab === "grid" ? "Grid Options" :
                      "Batch Options"} 
                     number="2" 
                     defaultOpen={true}>
            {renderSubTabContent()}
          </Accordion>
          
          <Accordion title="Output Settings" number="3">
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label htmlFor="outputWidth" className="mb-1 block text-sm">Width (px)</label>
                <input
                  id="outputWidth"
                  type="number"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  placeholder="1024"
                />
              </div>
              <div>
                <label htmlFor="outputHeight" className="mb-1 block text-sm">Height (px)</label>
                <input
                  id="outputHeight"
                  type="number"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  placeholder="1024"
                />
              </div>
            </div>
            
            <div className="mb-4">
              <label htmlFor="outputFormat" className="mb-1 block text-sm">Output Format:</label>
              <select id="outputFormat" className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                <option value="png">PNG</option>
                <option value="jpg">JPG</option>
                <option value="webp">WebP</option>
              </select>
            </div>
          </Accordion>
        </div>
      </div>
      
      {/* Right Column - Preview */}
      <div>
        <div className="rounded-md border border-border p-4 h-[500px] flex items-center justify-center overflow-hidden">
          {activeSubTab === "grid" ? (
            <div className="w-full h-full flex items-center justify-center">
              {isCreatingGrid ? (
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                  <p className="text-muted-foreground">Creating grid...</p>
                </div>
              ) : gridError ? (
                <div className="text-center">
                  <div className="text-red-500 mb-2">⚠️</div>
                  <p className="text-red-600 text-sm">{gridError}</p>
                </div>
              ) : gridResult ? (
                <div className="w-full h-full flex flex-col">
                  <img 
                    src={gridResult.grid_url} 
                    alt="Generated Grid" 
                    className="max-w-full max-h-full object-contain rounded"
                  />
                  <div className="mt-2 text-xs text-muted-foreground">
                    <p>{gridResult.dimensions.width}x{gridResult.dimensions.height} - {(gridResult.file_size / 1024).toFixed(1)}KB</p>
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-muted-foreground">Grid preview will display here</p>
                  <p className="text-sm text-muted-foreground mt-1">Click "Create Grid" to generate</p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center">
              <p className="text-muted-foreground">Processed image will display here</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ExtrasTab;
