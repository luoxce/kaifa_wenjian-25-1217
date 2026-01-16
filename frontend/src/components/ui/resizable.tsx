import * as ResizablePrimitive from "react-resizable-panels";

import { cn } from "@/lib/utils";

export const ResizablePanelGroup = ResizablePrimitive.PanelGroup;

export const ResizablePanel = ResizablePrimitive.Panel;

export function ResizableHandle({
  className,
  ...props
}: ResizablePrimitive.PanelResizeHandleProps) {
  return (
    <ResizablePrimitive.PanelResizeHandle
      className={cn(
        "relative flex w-px items-center justify-center bg-[#1c1c1c]",
        className
      )}
      {...props}
    >
      <div className="h-10 w-[2px] rounded-full bg-[#27272a]" />
    </ResizablePrimitive.PanelResizeHandle>
  );
}
