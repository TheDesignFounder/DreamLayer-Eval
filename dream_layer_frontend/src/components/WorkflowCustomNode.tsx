import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import type { WorkflowReactFlowNode } from '@/components/WorkflowGraph';

const MIN_NODE_HEIGHT = 80; // Minimum node height
const HANDLE_HEIGHT = 8; // Height of each handle
const VERTICAL_PADDING = 8; // Padding at top and bottom
const HANDLE_SPACING = 8; // Space between handles
const MAX_NODE_NAME_LENGTH = 18; // Maximum characters for node names
const MAX_HANDLE_NAME_LENGTH = 12; // Maximum characters for handle names

// Define color schemes
const NODE_COLORS = {
	purple: 'bg-purple-50 border-purple-200 dark:bg-purple-900/80 dark:border-purple-700',
	blue: 'bg-blue-50 border-blue-200 dark:bg-blue-900/80 dark:border-blue-700',
	green: 'bg-green-50 border-green-200 dark:bg-green-900/80 dark:border-green-700',
	red: 'bg-red-50 border-red-200 dark:bg-red-900/80 dark:border-red-700',
	yellow: 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/80 dark:border-yellow-700',
	orange: 'bg-orange-50 border-orange-200 dark:bg-orange-900/80 dark:border-orange-700',
	default: 'bg-background border-input dark:bg-slate-900/80 dark:border-slate-700'
};

// Map node types to colors
const NODE_TYPE_MAP: { [key: string]: string[] } = {
	purple: ['KSampler', 'SamplerCustom', 'KSamplerAdvanced'],
	blue: ['CheckpointLoaderSimple', 'VAELoader', 'UNETLoader', 'LoraLoader'],
	green: ['CLIPTextEncode', 'CLIPTextEncodeSDXL', 'CLIPLoader'],
	red: ['VAEDecode', 'VAEEncode'],
	yellow: ['SaveImage', 'PreviewImage', 'LoadImage'],
	orange: ['ControlNetLoader', 'ControlNetApply']
};

// Base node classes
const BASE_NODE_CLASSES = 'border hover:bg-accent hover:text-accent-foreground dark:hover:bg-slate-800 transition-colors';

const getNodeColor = (type: string) => {
	// Find the color for this node type
	const colorKey = Object.entries(NODE_TYPE_MAP).find(([_, types]) => 
		types.includes(type)
	)?.[0] || 'default';
	
	return `${BASE_NODE_CLASSES} ${NODE_COLORS[colorKey as keyof typeof NODE_COLORS]}`;
};

const calculateHandlePosition = (index: number) => {
	return VERTICAL_PADDING + 
				 (index * (HANDLE_HEIGHT + HANDLE_SPACING));
};

const truncateHandleName = (name: string) => {
	if (name.length <= MAX_HANDLE_NAME_LENGTH) return name;
	return name.substring(0, MAX_HANDLE_NAME_LENGTH) + '...';
};

const truncateNodeName = (name: string) => {
	if (name.length <= MAX_NODE_NAME_LENGTH) return name;
	return name.substring(0, MAX_NODE_NAME_LENGTH) + '...';
};

const WorkflowCustomNode: React.FC<NodeProps<WorkflowReactFlowNode>> = ({ data }) => {
  // Calculate dynamic node height based on handles
  const leftHandles = data.handles?.filter(h => h.position === 'left') || [];
  const rightHandles = data.handles?.filter(h => h.position === 'right') || [];
  
  const maxHandles = Math.max(leftHandles.length, rightHandles.length);
  const nodeHeight = Math.max(
    MIN_NODE_HEIGHT, 
    VERTICAL_PADDING * 3 + // Top padding + bottom padding + extra spacing
    maxHandles * HANDLE_HEIGHT + 
    Math.max(0, maxHandles - 1) * HANDLE_SPACING
  );

  return (
    <div 
      className={`
        px-4 py-2 
        shadow-md 
        rounded-md 
        w-80 
        relative
        transition-colors
        ${getNodeColor(data.nodeType)}
      `}
      style={{ height: `${nodeHeight}px` }}
    >
      {/* Left Handles */}
      <div className="absolute left-0 top-0 h-full w-4">
        {leftHandles.map((handle, index) => (
          <div 
            key={handle.id} 
            className="absolute flex items-center w-full"
            style={{ 
              top: `${calculateHandlePosition(index)}px`,
            }}
          >
            <Handle
              id={handle.id}
              type={handle.type}
              position={Position.Left}
              className="w-3 h-3 !bg-gray-500 opacity-50 hover:opacity-100"
            />
            <div className="ml-2 text-xs text-muted-foreground" title={handle.name}>
              {truncateHandleName(handle.name || '')}
            </div>
          </div>
        ))}
      </div>

      {/* Right Handles */}
      <div className="absolute right-0 top-0 h-full w-4">
        {rightHandles.map((handle, index) => (
          <div 
            key={handle.id} 
            className="absolute flex items-center w-full justify-end"
            style={{ 
              top: `${calculateHandlePosition(index)}px`,
            }}
          >
            <div className="mr-2 text-xs text-muted-foreground text-right" title={handle.name}>
              {truncateHandleName(handle.name || '')}
            </div>
            <Handle
              id={handle.id}
              type={handle.type}
              position={Position.Right}
              className="w-3 h-3 !bg-gray-500 opacity-50 hover:opacity-100"
            />
          </div>
        ))}
      </div>

      <div className="flex items-center h-full justify-center px-16">
        <div className="text-center w-full">
          <div className="text-sm font-bold text-foreground" title={data.label || data.nodeType}>
            {truncateNodeName(data.label || data.nodeType)}
          </div>
          <div className="text-xs text-muted-foreground mt-1" title={data.nodeType}>
            {truncateNodeName(data.nodeType)}
          </div>
        </div>
      </div>
    </div>
  );
};

export default memo(WorkflowCustomNode);
