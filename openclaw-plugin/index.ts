/**
 * claw-ea — OpenClaw Plugin
 *
 * Medical office automation: archives social media messages into
 * Obsidian notes, Apple Calendar events, and Apple Reminders.
 *
 * Wraps the Python MCP server as a native OpenClaw plugin.
 */
import { join } from "node:path";
import { existsSync } from "node:fs";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { McpBridge } from "./src/mcp-bridge.js";
import {
  createSaveAttachmentTool,
  createObsidianNoteTool,
  createCalendarEventTool,
  createReminderTool,
  createOcrImageTool,
  createDetectVaultTool,
  createListCalendarsTool,
  createConvertToMarkdownTool,
  createSaveConfigTool,
} from "./src/tools.js";

const DEFAULT_PROJECT_DIR = join(process.env.HOME ?? "", "Workspace/Claude/claw_EA");
const DEFAULT_PYTHON_PATH = join(DEFAULT_PROJECT_DIR, ".venv/bin/python");

const clawEaPlugin = {
  id: "claw-ea",
  name: "Claw EA",
  description: "Medical office automation — Obsidian, Apple Calendar, Reminders",

  register(api: OpenClawPluginApi) {
    const pluginCfg = api.pluginConfig ?? {};
    const enabled = pluginCfg.enabled !== false;
    const pythonPath = (pluginCfg.pythonPath as string) || DEFAULT_PYTHON_PATH;
    const projectDir = (pluginCfg.projectDir as string) || DEFAULT_PROJECT_DIR;

    if (!enabled) {
      api.logger.info("[claw-ea] Plugin disabled");
      return;
    }

    if (!existsSync(pythonPath)) {
      api.logger.warn(
        `[claw-ea] Python not found at ${pythonPath}. ` +
          `Run: cd ${projectDir} && uv sync`,
      );
      return;
    }

    const bridge = new McpBridge(pythonPath, projectDir);

    // Core workflow tools
    api.registerTool(() => createSaveAttachmentTool(bridge));
    api.registerTool(() => createObsidianNoteTool(bridge));
    api.registerTool(() => createCalendarEventTool(bridge));
    api.registerTool(() => createReminderTool(bridge));
    api.registerTool(() => createConvertToMarkdownTool(bridge));
    api.registerTool(() => createOcrImageTool(bridge));

    // Configuration tools
    api.registerTool(() => createDetectVaultTool(bridge));
    api.registerTool(() => createListCalendarsTool(bridge));
    api.registerTool(() => createSaveConfigTool(bridge));

    api.logger.info(
      `[claw-ea] Registered 9 tools (python=${pythonPath}, project=${projectDir})`,
    );
  },
};

export default clawEaPlugin;
