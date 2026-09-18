import React, { type FC } from 'react';
import {
  getBezierPath,
  EdgeLabelRenderer,
  BaseEdge,
  type EdgeProps,
  type Edge,
} from '@xyflow/react';

const WorkflowEdge: FC<EdgeProps<Edge<{ 
  sourceLabel?: string | null; 
  targetLabel?: string | null; 
}>>> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge 
        id={id} 
        path={edgePath} 
        style={{ 
          stroke: 'hsl(var(--muted-foreground))',
          strokeWidth: 2 
        }} 
      />
    </>
  );
};

export default WorkflowEdge;
