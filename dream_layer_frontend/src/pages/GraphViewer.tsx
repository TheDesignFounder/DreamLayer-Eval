import { useEffect, useState } from "react";
import ReactFlow, { Background, Controls, MiniMap } from "react-flow-renderer";
import graphData from "../assets/sample-graph.json";

const GraphViewer = () => {
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);


  useEffect(() => {
    const nodes: any[] = [];
    const edges: any[] = [];

    Object.entries(graphData.nodes).forEach(([id, node]: any, index) => {
      nodes.push({
        id,
        data: { label: node.class_type },
        position: { x: index * 200, y: index * 100 },
      });

      if (node.inputs) {
        Object.values(node.inputs).forEach((inputArr: any) => {
          inputArr.forEach((ref: any) => {
            const [sourceId] = ref;
            edges.push({
              id: `${sourceId}-${id}`,
              source: sourceId,
              target: id,
            });
          });
        });
      }
    });

    setNodes(nodes);
    setEdges(edges);

  }, []);

  return (
    <div style={{ height: "100vh" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodesDraggable={false}
        nodesConnectable={false}
        zoomOnScroll={false}
        panOnScroll={true}
      >
        <MiniMap />
        <Controls />
        <Background />
      </ReactFlow>
    </div>
  );
};

export default GraphViewer;
