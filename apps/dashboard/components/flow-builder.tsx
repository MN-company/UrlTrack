"use client";

import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { GitBranch, Lock, Mail, MousePointer2, ShieldAlert, Split, Webhook } from "lucide-react";
import { useMemo } from "react";

type FlowNodeData = {
  label: string;
  kind: "trigger" | "condition" | "action" | "split" | "end";
};

const nodes: Node<FlowNodeData>[] = [
  { id: "trigger", type: "urltrack", position: { x: 0, y: 80 }, data: { label: "Link Click", kind: "trigger" } },
  { id: "quality", type: "urltrack", position: { x: 240, y: 0 }, data: { label: "Traffic Quality > 65", kind: "condition" } },
  { id: "split", type: "urltrack", position: { x: 500, y: 80 }, data: { label: "A/B Split", kind: "split" } },
  { id: "redirect", type: "urltrack", position: { x: 760, y: 0 }, data: { label: "Redirect URL", kind: "action" } },
  { id: "gate", type: "urltrack", position: { x: 760, y: 170 }, data: { label: "Email Gate", kind: "action" } },
  { id: "end", type: "urltrack", position: { x: 1020, y: 80 }, data: { label: "Lead Created", kind: "end" } }
];

const edges: Edge[] = [
  { id: "trigger-quality", source: "trigger", target: "quality" },
  { id: "quality-split", source: "quality", target: "split" },
  { id: "split-redirect", source: "split", target: "redirect", label: "70%" },
  { id: "split-gate", source: "split", target: "gate", label: "30%" },
  { id: "redirect-end", source: "redirect", target: "end" },
  { id: "gate-end", source: "gate", target: "end" }
];

const icons = {
  action: Webhook,
  condition: ShieldAlert,
  end: Lock,
  split: Split,
  trigger: MousePointer2
};

function FlowNode({ data }: NodeProps<Node<FlowNodeData>>) {
  const Icon = icons[data.kind] ?? GitBranch;
  return (
    <div className="min-w-44 rounded-ui border border-border bg-panel px-3 py-2 shadow-xl shadow-black/20">
      <Handle type="target" position={Position.Left} />
      <div className="flex items-center gap-2">
        <Icon className="size-4 text-live" aria-hidden="true" />
        <span className="text-xs uppercase text-muted">{data.kind}</span>
      </div>
      <div className="mt-2 text-sm">{data.label}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function FlowBuilder() {
  const nodeTypes = useMemo(() => ({ urltrack: FlowNode }), []);

  return (
    <div className="h-[480px] overflow-hidden rounded-ui border border-border bg-obsidian">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
        <Background color="#2A2A2A" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
