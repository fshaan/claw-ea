/**
 * OpenClaw tool definitions for claw-ea.
 * Each tool delegates to the Python MCP server via McpBridge.
 */
import { Type } from "@sinclair/typebox";
import type { McpBridge } from "./mcp-bridge.js";

interface ToolResult {
  content: Array<{ type: "text"; text: string }>;
}

function textResult(text: string): ToolResult {
  return { content: [{ type: "text", text }] };
}

export function createSaveAttachmentTool(bridge: McpBridge) {
  return {
    name: "claw_save_attachment",
    label: "保存附件",
    description:
      "Save a file to the attachments directory, organized by date. " +
      "Two modes: file_path (local path, preferred) or file_content (base64). " +
      "Skips duplicates. Handles Chinese filenames.",
    parameters: Type.Object({
      file_path: Type.Optional(Type.String({ description: 'Local file path (preferred). e.g. "/tmp/openclaw/media/手术通知.pdf"' })),
      file_content: Type.Optional(Type.String({ description: "Base64-encoded file content (use file_path instead when file is local)" })),
      filename: Type.Optional(Type.String({ description: "Override filename. Required for file_content, optional for file_path." })),
      subfolder: Type.Optional(Type.String({ description: "Optional subdirectory" })),
    }),
    async execute(_id: string, params: { file_path?: string; file_content?: string; filename?: string; subfolder?: string }) {
      const result = await bridge.callTool("save_attachment", params);
      return textResult(result);
    },
  };
}

export function createObsidianNoteTool(bridge: McpBridge) {
  return {
    name: "claw_create_note",
    label: "创建笔记",
    description:
      "Create an Obsidian note with YAML frontmatter. Deduplicates by content hash. " +
      "Categories: surgery, meeting, meeting_minutes, task, document, general.",
    parameters: Type.Object({
      category: Type.String({ description: "surgery | meeting | meeting_minutes | task | document | general" }),
      title: Type.String({ description: "Note title" }),
      content_data: Type.Any({ description: "Structured data extracted from the message (JSON object)" }),
      attachment_paths: Type.Optional(Type.Array(Type.String(), { description: "Paths from save_attachment" })),
    }),
    async execute(_id: string, params: { category: string; title: string; content_data: unknown; attachment_paths?: string[] }) {
      const result = await bridge.callTool("create_obsidian_note", params);
      return textResult(result);
    },
  };
}

export function createCalendarEventTool(bridge: McpBridge) {
  return {
    name: "claw_create_calendar_event",
    label: "创建日历事件",
    description:
      "Create an event in Apple Calendar. Default duration: 1 hour.",
    parameters: Type.Object({
      title: Type.String({ description: "Event title" }),
      start_time: Type.String({ description: "ISO-8601 datetime" }),
      end_time: Type.Optional(Type.String({ description: "ISO-8601. Defaults to start + 1 hour" })),
      location: Type.Optional(Type.String({ description: "Event location" })),
      notes: Type.Optional(Type.String({ description: "Additional notes" })),
    }),
    async execute(_id: string, params: { title: string; start_time: string; end_time?: string; location?: string; notes?: string }) {
      const result = await bridge.callTool("create_calendar_event", params);
      return textResult(result);
    },
  };
}

export function createReminderTool(bridge: McpBridge) {
  return {
    name: "claw_create_reminder",
    label: "创建提醒",
    description: "Create a reminder in Apple Reminders. Supports due date and priority (1-9).",
    parameters: Type.Object({
      title: Type.String({ description: "Reminder title" }),
      due_date: Type.Optional(Type.String({ description: "ISO-8601 datetime" })),
      priority: Type.Optional(Type.Number({ description: "1-9 (1=highest)" })),
      notes: Type.Optional(Type.String({ description: "Additional notes" })),
    }),
    async execute(_id: string, params: { title: string; due_date?: string; priority?: number; notes?: string }) {
      const result = await bridge.callTool("create_reminder", params);
      return textResult(result);
    },
  };
}

export function createOcrImageTool(bridge: McpBridge) {
  return {
    name: "claw_ocr_image",
    label: "图片OCR",
    description:
      "Extract text from an image using local OCR (macOS Vision). " +
      "Use only when the LLM cannot see images directly.",
    parameters: Type.Object({
      image_content: Type.String({ description: "Base64-encoded image data" }),
      filename: Type.String({ description: "Original filename" }),
    }),
    async execute(_id: string, params: { image_content: string; filename: string }) {
      const result = await bridge.callTool("ocr_image", params);
      return textResult(result);
    },
  };
}

export function createDetectVaultTool(bridge: McpBridge) {
  return {
    name: "claw_detect_vault",
    label: "检测Obsidian",
    description: "Scan common locations for Obsidian vaults.",
    parameters: Type.Object({}),
    async execute() {
      const result = await bridge.callTool("detect_obsidian_vault");
      return textResult(result);
    },
  };
}

export function createListCalendarsTool(bridge: McpBridge) {
  return {
    name: "claw_list_calendars",
    label: "列出日历",
    description: "List available Apple Calendar calendars and Reminder lists.",
    parameters: Type.Object({}),
    async execute() {
      const result = await bridge.callTool("list_apple_calendars");
      return textResult(result);
    },
  };
}

export function createSaveConfigTool(bridge: McpBridge) {
  return {
    name: "claw_save_config",
    label: "保存配置",
    description: "Validate and save configuration to ~/.claw-ea/config.yaml.",
    parameters: Type.Object({
      config_data: Type.Any({ description: "Configuration dictionary" }),
    }),
    async execute(_id: string, params: { config_data: unknown }) {
      const result = await bridge.callTool("save_config", params);
      return textResult(result);
    },
  };
}
