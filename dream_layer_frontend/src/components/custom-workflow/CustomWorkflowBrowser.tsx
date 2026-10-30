import React, { useState, useRef } from 'react';
import { Upload, FileText, X, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface CustomWorkflowBrowserProps {
  onWorkflowChange: (workflow: import('@/types/api').CustomWorkflow) => void;
  currentWorkflow?: import('@/types/api').CustomWorkflow;
}

const CustomWorkflowBrowser: React.FC<CustomWorkflowBrowserProps> = ({ 
  onWorkflowChange, 
  currentWorkflow 
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
      setError('Please select a valid JSON file');
      return;
    }

    setIsUploading(true);
    setError(null);

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const workflow = JSON.parse(e.target?.result as string);
        
        // Basic validation - check if it has a "prompt" key
        if (!workflow.prompt) {
          throw new Error('Invalid workflow: missing "prompt" key');
        }

        onWorkflowChange(workflow);
        setError(null);
      } catch (err) {
        setError('Invalid JSON file or workflow format');
        console.error('Workflow parsing error:', err);
      } finally {
        setIsUploading(false);
      }
    };

    reader.onerror = () => {
      setError('Failed to read file');
      setIsUploading(false);
    };

    reader.readAsText(file);
  };

  const handleRefreshClick = () => {
    fileInputRef.current?.click();
  };

  const clearWorkflow = () => {
    onWorkflowChange(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-4">
      {/* File Upload Section */}
      <div className="border-2 border-dashed border-border rounded-lg p-6 text-center">
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={handleFileSelect}
          className="hidden"
        />
        
        {!currentWorkflow ? (
          <div className="space-y-4">
            <Upload className="mx-auto h-12 w-12 text-muted-foreground" />
            <div>
              <h3 className="text-lg font-medium">Upload Custom Workflow</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Select a JSON file containing your ComfyUI workflow
              </p>
            </div>
            <Button
              onClick={handleRefreshClick}
              disabled={isUploading}
              variant="outline"
              className="mt-4 flex items-center gap-2 mx-auto"
            >
              <RefreshCw className={`h-4 w-4 ${isUploading ? 'animate-spin' : ''}`} />
              {isUploading ? 'Uploading...' : 'Select Workflow File'}
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <FileText className="mx-auto h-8 w-8 text-green-600" />
            <div>
              <h3 className="text-lg font-medium text-green-600">Workflow Loaded</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Custom workflow is ready to use
              </p>
            </div>
            <div className="flex gap-2 justify-center">
              <Button 
                onClick={handleRefreshClick}
                variant="outline"
                className="flex items-center gap-2"
              >
                <RefreshCw className="h-4 w-4" />
                Replace Workflow
              </Button>
              <Button 
                onClick={clearWorkflow}
                variant="outline"
                className="flex items-center gap-2"
              >
                <X className="h-4 w-4" />
                Clear Workflow
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {/* Workflow Preview */}
      {currentWorkflow && (
        <div className="border border-border rounded-md p-4">
          <h4 className="font-medium mb-2">Workflow Preview</h4>
          <div className="bg-muted rounded p-3 text-sm">
            <p><strong>Nodes:</strong> {Object.keys(currentWorkflow.prompt || {}).length}</p>
            <p><strong>Type:</strong> Custom Workflow</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomWorkflowBrowser; 