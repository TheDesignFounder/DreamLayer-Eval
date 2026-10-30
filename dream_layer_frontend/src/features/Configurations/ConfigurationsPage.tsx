import React, { useRef } from 'react';
import Accordion from '@/components/Accordion';
import Slider from '@/components/Slider';
import { useSettingsStore } from './useSettingsStore';

const ConfigurationsPage = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const outputDirRef = useRef<HTMLInputElement>(null);
  const modelsDirRef = useRef<HTMLInputElement>(null);
  const controlNetRef = useRef<HTMLInputElement>(null);
  const upscalerRef = useRef<HTMLInputElement>(null);
  const vaeRef = useRef<HTMLInputElement>(null);
  const loraRef = useRef<HTMLInputElement>(null);

  const {
    uiTheme, setUiTheme,
    showQuickSettings, setShowQuickSettings,
    showProgressInTitle, setShowProgressInTitle,
    computeDevice, setComputeDevice,
    vramUsageTarget, setVramUsageTarget,
    parallelProcessing, setParallelProcessing,
    useXformers, setUseXformers,
    optimizeMedVram, setOptimizeMedVram,
    outputDirectory, setOutputDirectory,
    modelsDirectory, setModelsDirectory,
    controlNetModelsPath, setControlNetModelsPath,
    upscalerModelsPath, setUpscalerModelsPath,
    vaeModelsPath, setVaeModelsPath,
    loraEmbeddingsPath, setLoraEmbeddingsPath,
    filenameFormat, setFilenameFormat,
    saveMetadata, setSaveMetadata,
    autoUpdate, setAutoUpdate
  } = useSettingsStore();

  const handleSaveSettings = async () => {
    try {
      const pathSettings = {
        outputDirectory,
        modelsDirectory,
        controlNetModelsPath,
        upscalerModelsPath,
        vaeModelsPath,
        loraEmbeddingsPath,
        filenameFormat,
        saveMetadata
      };

      const response = await fetch('http://localhost:5002/api/settings/paths', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(pathSettings),
      });

      const data = await response.json();
      
      if (data.status === 'success') {
        // TODO: Add a toast notification for success
        console.log('Settings saved successfully');
      } else {
        throw new Error(data.message);
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      // TODO: Add a toast notification for error
    }
  };

  const handleDirectoryBrowse = async (
    setter: (path: string) => void,
    fileInputRef: React.RefObject<HTMLInputElement>
  ) => {
    try {
      if ('showDirectoryPicker' in window) {
        const dirHandle = await (window as Window & { showDirectoryPicker: () => Promise<{ name: string }> }).showDirectoryPicker();
        setter(dirHandle.name);
      } else {
        fileInputRef.current?.click();
      }
    } catch (error) {
      console.error('Error selecting directory:', error);
      fileInputRef.current?.click();
    }
  };

  const handleFileInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
    setter: (path: string) => void
  ) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      const path = files[0].webkitRelativePath || files[0].name;
      setter(path);
    }
  };

  return (
    <div className="mb-4">
      <div className="flex flex-col">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-medium">System Configurations</h3>
          <button 
            onClick={handleSaveSettings}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Save Settings
          </button>
        </div>
        
        <Accordion title="UI Settings" number="1" defaultOpen={true}>
          <div className="mb-4">
            <label htmlFor="uiTheme" className="mb-1 block text-sm font-medium">UI Theme:</label>
            <select 
              id="uiTheme" 
              value={uiTheme}
              onChange={(e) => setUiTheme(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="system">System Default</option>
              <option value="light">Light Mode</option>
              <option value="dark">Dark Mode</option>
            </select>
          </div>
          
          <div className="flex items-center mb-4">
            <input 
              type="checkbox" 
              id="quicksettings" 
              checked={showQuickSettings}
              onChange={(e) => setShowQuickSettings(e.target.checked)}
              className="mr-2" 
            />
            <label htmlFor="quicksettings" className="text-sm">Show quick settings</label>
          </div>
          
          <div className="flex items-center mb-4">
            <input 
              type="checkbox" 
              id="progressInTitle" 
              checked={showProgressInTitle}
              onChange={(e) => setShowProgressInTitle(e.target.checked)}
              className="mr-2" 
            />
            <label htmlFor="progressInTitle" className="text-sm">Show progress in title</label>
          </div>
        </Accordion>
        
        <div style={{ display: 'none' }}><Accordion title="Performance & Resources" number="2" defaultOpen={true}>
          <div className="mb-4">
            <label htmlFor="computeDevice" className="mb-1 block text-sm font-medium">Primary Compute Device:</label>
            <select 
              id="computeDevice" 
              value={computeDevice}
              onChange={(e) => setComputeDevice(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="cuda">NVIDIA GPU (CUDA)</option>
              <option value="rocm">AMD GPU (ROCm)</option>
              <option value="mps">Apple Silicon (MPS)</option>
              <option value="cpu">CPU</option>
            </select>
          </div>
          
          <Slider
            min={0}
            max={100}
            defaultValue={vramUsageTarget}
            label="VRAM Usage Target (%)"
            sublabel="| Lower to reduce memory usage"
            onChange={setVramUsageTarget}
          />
          
          <Slider
            min={1}
            max={16}
            defaultValue={parallelProcessing}
            label="Parallel Processing"
            sublabel="| Higher values use more GPU memory"
            onChange={setParallelProcessing}
          />
          
          <div className="flex items-center mb-4">
            <input 
              type="checkbox" 
              id="xformers" 
              checked={useXformers}
              onChange={(e) => setUseXformers(e.target.checked)}
              className="mr-2" 
            />
            <label htmlFor="xformers" className="text-sm">Use xFormers memory efficient attention</label>
          </div>
          
          <div className="flex items-center mb-4">
            <input 
              type="checkbox" 
              id="medvram" 
              checked={optimizeMedVram}
              onChange={(e) => setOptimizeMedVram(e.target.checked)}
              className="mr-2" 
            />
            <label htmlFor="medvram" className="text-sm">Optimize for medium-low VRAM usage</label>
          </div>
        </Accordion></div>
        
        <Accordion title="Paths & Saving" number="2">
          <div className="mb-4">
            <label htmlFor="outputDir" className="mb-1 block text-sm font-medium">Output Directory:</label>
            <div className="flex">
              <input
                id="outputDir"
                type="text"
                value={outputDirectory}
                onChange={(e) => setOutputDirectory(e.target.value)}
                className="flex-1 rounded-l-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="/path/to/outputs"
              />
              <button
                type="button"
                onClick={() => handleDirectoryBrowse(setOutputDirectory, outputDirRef)}
                className="rounded-r-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground"
              >
                Browse
              </button>
              <input
                ref={outputDirRef}
                type="file"
                webkitdirectory=""
                style={{ display: 'none' }}
                onChange={(e) => handleFileInputChange(e, setOutputDirectory)}
              />
            </div>
          </div>
          
          <div className="mb-4">
            <label htmlFor="modelsDir" className="mb-1 block text-sm font-medium">Models Directory:</label>
            <div className="flex">
              <input
                id="modelsDir"
                type="text"
                value={modelsDirectory}
                onChange={(e) => setModelsDirectory(e.target.value)}
                className="flex-1 rounded-l-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="/path/to/models"
              />
              <button
                type="button"
                onClick={() => handleDirectoryBrowse(setModelsDirectory, modelsDirRef)}
                className="rounded-r-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground"
              >
                Browse
              </button>
              <input
                ref={modelsDirRef}
                type="file"
                webkitdirectory=""
                style={{ display: 'none' }}
                onChange={(e) => handleFileInputChange(e, setModelsDirectory)}
              />
            </div>
          </div>

          <div className="mb-4">
            <label htmlFor="controlNetModelsPath" className="mb-1 block text-sm font-medium">ControlNet Models Path:</label>
            <div className="flex">
              <input
                id="controlNetModelsPath"
                type="text"
                value={controlNetModelsPath}
                onChange={(e) => setControlNetModelsPath(e.target.value)}
                className="flex-1 rounded-l-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="/path/to/models/ControlNet"
              />
              <button
                type="button"
                onClick={() => handleDirectoryBrowse(setControlNetModelsPath, controlNetRef)}
                className="rounded-r-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground"
              >
                Browse
              </button>
              <input
                ref={controlNetRef}
                type="file"
                webkitdirectory=""
                style={{ display: 'none' }}
                onChange={(e) => handleFileInputChange(e, setControlNetModelsPath)}
              />
            </div>
          </div>

          <div className="mb-4">
            <label htmlFor="upscalerModelsPath" className="mb-1 block text-sm font-medium">Upscaler Models Path:</label>
            <div className="flex">
              <input
                id="upscalerModelsPath"
                type="text"
                value={upscalerModelsPath}
                onChange={(e) => setUpscalerModelsPath(e.target.value)}
                className="flex-1 rounded-l-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="/path/to/models/ESRGAN"
              />
              <button
                type="button"
                onClick={() => handleDirectoryBrowse(setUpscalerModelsPath, upscalerRef)}
                className="rounded-r-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground"
              >
                Browse
              </button>
              <input
                ref={upscalerRef}
                type="file"
                webkitdirectory=""
                style={{ display: 'none' }}
                onChange={(e) => handleFileInputChange(e, setUpscalerModelsPath)}
              />
            </div>
          </div>

          <div className="mb-4">
            <label htmlFor="vaeModelsPath" className="mb-1 block text-sm font-medium">VAE Models Path:</label>
            <div className="flex">
              <input
                id="vaeModelsPath"
                type="text"
                value={vaeModelsPath}
                onChange={(e) => setVaeModelsPath(e.target.value)}
                className="flex-1 rounded-l-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="/path/to/models/VAE"
              />
              <button
                type="button"
                onClick={() => handleDirectoryBrowse(setVaeModelsPath, vaeRef)}
                className="rounded-r-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground"
              >
                Browse
              </button>
              <input
                ref={vaeRef}
                type="file"
                webkitdirectory=""
                style={{ display: 'none' }}
                onChange={(e) => handleFileInputChange(e, setVaeModelsPath)}
              />
            </div>
          </div>

          <div className="mb-4">
            <label htmlFor="loraEmbeddingsPath" className="mb-1 block text-sm font-medium">LoRA / Embeddings Path:</label>
            <div className="flex">
              <input
                id="loraEmbeddingsPath"
                type="text"
                value={loraEmbeddingsPath}
                onChange={(e) => setLoraEmbeddingsPath(e.target.value)}
                className="flex-1 rounded-l-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="/path/to/models/Lora"
              />
              <button
                type="button"
                onClick={() => handleDirectoryBrowse(setLoraEmbeddingsPath, loraRef)}
                className="rounded-r-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground"
              >
                Browse
              </button>
              <input
                ref={loraRef}
                type="file"
                webkitdirectory=""
                style={{ display: 'none' }}
                onChange={(e) => handleFileInputChange(e, setLoraEmbeddingsPath)}
              />
            </div>
          </div>
          
          <div className="mb-4">
            <label htmlFor="filenameFormat" className="mb-1 block text-sm font-medium">Filename Format:</label>
            <input
              id="filenameFormat"
              type="text"
              value={filenameFormat}
              onChange={(e) => setFilenameFormat(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="[model_name]_[seed]_[prompt_words]"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Variables: [seed], [model_name], [prompt_words], [width], [height], [steps], [date], [time]
            </p>
          </div>
          
          <div className="flex items-center mb-4">
            <input 
              type="checkbox" 
              id="saveMetadata" 
              checked={saveMetadata}
              onChange={(e) => setSaveMetadata(e.target.checked)}
              className="mr-2" 
            />
            <label htmlFor="saveMetadata" className="text-sm">Save generation parameters as metadata</label>
          </div>
        </Accordion>
        
        <Accordion title="Updates & Installation" number="3">
          <div className="flex items-center justify-between mb-4 p-4 bg-muted rounded-md">
            <div>
              <p className="font-medium">Current Version: v1.2.3</p>
              <p className="text-xs text-muted-foreground">Last checked: 4 hours ago</p>
            </div>
            <button className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground">
              Check for Updates
            </button>
          </div>
          
          <div className="flex items-center mb-4">
            <input 
              type="checkbox" 
              id="autoUpdate" 
              checked={autoUpdate}
              onChange={(e) => setAutoUpdate(e.target.checked)}
              className="mr-2" 
            />
            <label htmlFor="autoUpdate" className="text-sm">Enable automatic updates</label>
          </div>
        </Accordion>
      </div>
    </div>
  );
};

export default ConfigurationsPage;
