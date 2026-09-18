import React, { useEffect, useRef, useCallback } from 'react';
import demoWorkflow from '@/data/demo-workflow.json';

// Type definitions for ComfyUI workflow
interface WorkflowNodeInput {
  name: string;
  type: string;
  link?: number;
}

interface WorkflowNodeOutput {
  name: string;
  type: string;
  links?: number[];
  slot_index?: number;
}

interface WorkflowNode {
  id: number;
  type: string;
  pos?: [number, number];
  size?: [number, number];
  inputs?: WorkflowNodeInput[];
  outputs?: WorkflowNodeOutput[];
  properties?: Record<string, unknown>;
  widgets_values?: (string | number | boolean)[];
  title?: string;
}

interface WorkflowLink {
  [0]: number; // link ID
  [1]: number; // source node ID
  [2]: number; // source output index
  [3]: number; // target node ID
  [4]: number; // target input index
  [5]: string; // connection type
}

interface WorkflowData {
  nodes: WorkflowNode[];
  links: WorkflowLink[];
}

interface WorkflowUploaderProps {
  onWorkflowLoaded: (data: WorkflowData) => void;
}

// Runtime type guard to validate WorkflowData
function isWorkflowData(obj: unknown): obj is WorkflowData {
  if (!obj || typeof obj !== 'object') {
    return false;
  }

  const data = obj as Record<string, unknown>;

  // Check if nodes exists and is an array
  if (!Array.isArray(data.nodes)) {
    return false;
  }

  // Check if links exists and is an array
  if (!Array.isArray(data.links)) {
    return false;
  }

  // Validate each node has required properties
  for (const node of data.nodes) {
    if (!node || typeof node !== 'object') {
      return false;
    }
    const nodeObj = node as Record<string, unknown>;
    if (typeof nodeObj.id !== 'number' || typeof nodeObj.type !== 'string') {
      return false;
    }
  }

  // Validate each link is an array with expected structure
  for (const link of data.links) {
    if (!Array.isArray(link) || link.length < 6) {
      return false;
    }
  }

  return true;
}

export const WorkflowUploader: React.FC<WorkflowUploaderProps> = ({ onWorkflowLoaded }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Reusable demo loading logic
  const loadDemoWorkflow = useCallback(() => {
    if (isWorkflowData(demoWorkflow)) {
      onWorkflowLoaded(demoWorkflow);
    } else {
      console.error('Demo workflow data is invalid');
      alert('Demo workflow data is corrupted. Please refresh the page.');
    }
  }, [onWorkflowLoaded]);
  
  // Load demo workflow on component mount
  useEffect(() => {
    loadDemoWorkflow();
  }, [loadDemoWorkflow]);
  
  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const parsedData = JSON.parse(e.target?.result as string);
          
          if (!isWorkflowData(parsedData)) {
            throw new Error('Invalid workflow data format. Expected nodes and links arrays with proper structure.');
          }
          
          onWorkflowLoaded(parsedData);
        } catch (error) {
          console.error('Error processing workflow JSON', error);
          const errorMessage = error instanceof Error ? error.message : 'Failed to parse workflow JSON. Please check the file format.';
          alert(errorMessage);
        } finally {
          // Reset the input value so the same file can be uploaded again
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
        }
      };
      reader.readAsText(file);
    } else {
      // Also reset if no file is selected (e.g., user cancels dialog)
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const loadDemo = () => {
    loadDemoWorkflow();
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={loadDemo}
        className="inline-flex items-center gap-2 rounded-md bg-secondary px-3 py-2 text-sm font-medium text-secondary-foreground hover:bg-secondary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="5,3 19,12 5,21"/>
        </svg>
        Demo
      </button>
      <label 
        htmlFor="workflow-upload-input"
        className="cursor-pointer inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
          <polyline points="14,2 14,8 20,8"/>
        </svg>
        Upload JSON
      </label>
      <input
        ref={fileInputRef}
        id="workflow-upload-input"
        type="file"
        accept="application/json"
        onChange={handleFileUpload}
        className="hidden"
      />
    </div>
  );
};

export type { WorkflowData, WorkflowNode, WorkflowLink, WorkflowNodeInput, WorkflowNodeOutput };
