import React, { useCallback, useMemo, useRef, useEffect, useState } from 'react';
import {
  ReactFlow,
  addEdge,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  Connection,
  ConnectionLineType,
  OnConnect,
  ReactFlowInstance,
  FitViewOptions,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './WorkflowGraph.css';
import WorkflowCustomNode from '@/components/WorkflowCustomNode';
import WorkflowEdge from '@/components/WorkflowEdge';
import { WorkflowUploader, WorkflowData, WorkflowNodeInput, WorkflowNodeOutput } from '@/components/WorkflowUploader';

// Custom node data type
interface WorkflowNodeData extends Record<string, unknown> {
  label: string;
  nodeType: string;
  inputs?: Array<{ name: string; type: string }>;
  outputs?: Array<{ name: string; type: string }>;
  handles?: Array<{
    id: string;
    type: 'source' | 'target';
    position: 'left' | 'right';
    name?: string;
    index: number;
  }>;
  widgetValues?: (string | number | boolean)[];
}

// Custom edge data type
interface WorkflowEdgeData extends Record<string, unknown> {
  sourceLabel?: string;
  targetLabel?: string;
}

// Typed nodes and edges  
export type WorkflowReactFlowNode = Node<WorkflowNodeData, 'workflow'>;
export type WorkflowReactFlowEdge = Edge<WorkflowEdgeData>;

export const WorkflowGraph: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowReactFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<WorkflowReactFlowEdge>([]);
  const reactFlowInstance = useRef<ReactFlowInstance | null>(null);

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({
        ...connection,
        data: {
          sourceLabel: connection.sourceHandle,
          targetLabel: connection.targetHandle,
        },
      }, eds));
    },
    [setEdges],
  );

  const fitViewOptions: FitViewOptions = useMemo(() => ({
    padding: 0.1,
    duration: 240,
    interpolate: "smooth" as const
  }), []);

  const parseWorkflowJson = useCallback((jsonData: WorkflowData) => {
    // Create maps to track node details
    const nodeInputMap = new Map<string, WorkflowNodeInput[]>();
    const nodeOutputMap = new Map<string, WorkflowNodeOutput[]>();
    
    // Prepare nodes with correct inputs and outputs
    const processedNodes: WorkflowReactFlowNode[] = jsonData.nodes.map((node) => {
      // Store original inputs and outputs
      nodeInputMap.set(node.id.toString(), node.inputs || []);
      nodeOutputMap.set(node.id.toString(), node.outputs || []);

      // Generate input handles
      const inputHandles = (node.inputs || []).map((input, index) => ({
        id: `input-${input.name}`,
        type: 'target' as const,
        position: 'left' as const,
        name: input.name,
        index: index
      }));

      // Generate output handles
      const outputHandles = (node.outputs || []).map((output, index) => ({
        id: `output-${output.name}`,
        type: 'source' as const,
        position: 'right' as const,
        name: output.name,
        index: index
      }));

      return {
        id: node.id.toString(),
        type: 'workflow',
        position: {
          x: node.pos?.[0] || 0,
          y: node.pos?.[1] || 0,
        },
        data: {
          label: node.title || node.type,
          nodeType: node.type,
          inputs: node.inputs?.map((input) => ({
            name: input.name,
            type: input.type,
          })),
          outputs: node.outputs?.map((output) => ({
            name: output.name,
            type: output.type,
          })),
          handles: [...inputHandles, ...outputHandles],
          widgetValues: node.widgets_values,
        },
      };
    });

    // Prepare edges with explicit handle IDs
    const processedEdges: WorkflowReactFlowEdge[] = jsonData.links.map((link) => {
      const sourceNodeId = link[1].toString();
      const targetNodeId = link[3].toString();
      
      // Get the input name for the target node's specific input index
      const targetInputs = nodeInputMap.get(targetNodeId) || [];
      const sourceOutputs = nodeOutputMap.get(sourceNodeId) || [];

      const targetInputName = targetInputs[link[4]]?.name || `input-${link[4]}`;
      const sourceOutputName = sourceOutputs[link[2]]?.name || `output-${link[2]}`;

      return {
        id: `e${link[0]}`,
        source: sourceNodeId,
        target: targetNodeId,
        sourceHandle: `output-${sourceOutputName}`,
        targetHandle: `input-${targetInputName}`,
        type: 'default',
        data: {
          sourceLabel: sourceOutputName,
          targetLabel: targetInputName,
        },
      };
    });

    setNodes(processedNodes);
    setEdges(processedEdges);
    
    // Fit view after setting new nodes/edges
    let fitViewTimeoutId: NodeJS.Timeout;
    if (reactFlowInstance.current) {
      fitViewTimeoutId = setTimeout(() => {
        reactFlowInstance.current?.fitView(fitViewOptions);
      }, 240);
    }
    return () => {
      if (fitViewTimeoutId) {
        clearTimeout(fitViewTimeoutId);
      }
    };
  }, [fitViewOptions, setNodes, setEdges]);

  const handleWorkflowLoaded = useCallback((jsonData: WorkflowData) => {
    parseWorkflowJson(jsonData);
  }, [parseWorkflowJson]);

  const onInit = useCallback((instance: ReactFlowInstance) => {
    reactFlowInstance.current = instance;
    instance.fitView(fitViewOptions);
  }, [fitViewOptions]);

  // Memoize node and edge types to prevent unnecessary re-renders
  const nodeTypes = useMemo(() => ({
    workflow: WorkflowCustomNode,
  }), []);

  const edgeTypes = useMemo(() => ({
    default: WorkflowEdge,
  }), []);

  return (
    <div className="w-full h-screen flex flex-col">
      <div className="flex items-center justify-between border-b border-border bg-background px-4 py-2">
        <h1 className="text-lg font-medium text-primary">DreamLayer ComfyUI Workflow Graph</h1>
        <WorkflowUploader onWorkflowLoaded={handleWorkflowLoaded} />
      </div>
      <div className="flex-1">
        <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onInit={onInit}
        connectionLineType={ConnectionLineType.Straight}
				nodesConnectable={false}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap 
          nodeColor="hsl(var(--muted))"
          nodeStrokeColor="hsl(var(--border))"
          nodeStrokeWidth={1}
          nodeBorderRadius={3}
        />
      </ReactFlow>
      </div>
    </div>
  );
};
