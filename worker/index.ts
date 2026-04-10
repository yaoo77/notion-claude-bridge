/**
 * Notion AI → GitHub Bridge MCP Server
 * Cloudflare Agents SDK (McpAgent) ベースの Streamable HTTP 対応版
 */

import { McpAgent } from "agents/mcp";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

interface Env {
  GITHUB_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  MCP_AUTH_TOKEN: string;
  MCP_OBJECT: DurableObjectNamespace;
}

// GitHub API helper
async function githubAPI(
  env: Env,
  path: string,
  method: string = "GET",
  body?: unknown
): Promise<Response> {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}${path}`;
  return fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github.v3+json",
      "User-Agent": "notion-claude-bridge",
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

// McpAgent Durable Object
export class NotionClaudeBridge extends McpAgent<Env, {}, { login?: string }> {
  server = new McpServer({
    name: "notion-claude-bridge",
    version: "1.0.0",
  });

  async authenticate(req: Request): Promise<{ login?: string }> {
    const auth = req.headers.get("Authorization");
    if (!auth?.startsWith("Bearer ")) {
      throw new Response("Unauthorized", { status: 401 });
    }
    if (auth.slice(7) !== this.env.MCP_AUTH_TOKEN) {
      throw new Response("Forbidden", { status: 403 });
    }
    return { login: "notion-agent" };
  }

  async init() {
    // Tool: create_issue
    this.server.tool(
      "create_issue",
      "GitHub Issueを作成し、Claude Code（GitHub Actions）を起動します。本文に実装指示を書くと、Claude Codeが自動でPRを作成します。",
      {
        title: z.string().describe("Issueのタイトル"),
        body: z.string().describe("Issueの本文。Claude Codeへの実装指示を含めてください。"),
        labels: z.array(z.string()).optional().describe("ラベル（省略可）"),
      },
      async ({ title, body, labels }) => {
        const res = await githubAPI(this.env, "/issues", "POST", {
          title,
          body,
          labels: labels || [],
        });
        const data = (await res.json()) as Record<string, unknown>;
        if (!res.ok)
          return {
            content: [
              { type: "text" as const, text: `Error: ${JSON.stringify(data)}` },
            ],
            isError: true,
          };
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(
                {
                  issue_number: data.number,
                  url: data.html_url,
                  message: `Issue #${data.number} を作成しました。Claude Codeが自動で処理を開始します。`,
                },
                null,
                2
              ),
            },
          ],
        };
      }
    );

    // Tool: comment_on_issue
    this.server.tool(
      "comment_on_issue",
      "既存のIssueまたはPRにコメントを投稿します。@claudeを含めるとClaude Codeが反応して追加作業を行います。",
      {
        issue_number: z.number().describe("IssueまたはPRの番号"),
        body: z.string().describe("コメント本文。Claude Codeに指示する場合は @claude を含めてください。"),
      },
      async ({ issue_number, body }) => {
        const res = await githubAPI(
          this.env,
          `/issues/${issue_number}/comments`,
          "POST",
          { body }
        );
        const data = (await res.json()) as Record<string, unknown>;
        if (!res.ok)
          return {
            content: [
              { type: "text" as const, text: `Error: ${JSON.stringify(data)}` },
            ],
            isError: true,
          };
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(
                {
                  comment_url: data.html_url,
                  message: `Issue/PR #${issue_number} にコメントしました。`,
                },
                null,
                2
              ),
            },
          ],
        };
      }
    );

    // Tool: list_pull_requests
    this.server.tool(
      "list_pull_requests",
      "リポジトリのPR一覧を取得します。Claude Codeが作成したPRの状況確認に使います。",
      {
        state: z
          .enum(["open", "closed", "all"])
          .optional()
          .default("open")
          .describe("PRの状態（デフォルト: open）"),
      },
      async ({ state }) => {
        const res = await githubAPI(this.env, `/pulls?state=${state}`);
        const data = (await res.json()) as Array<Record<string, unknown>>;
        if (!res.ok)
          return {
            content: [
              { type: "text" as const, text: `Error: ${JSON.stringify(data)}` },
            ],
            isError: true,
          };
        const prs = data.map((pr) => ({
          number: pr.number,
          title: pr.title,
          state: pr.state,
          url: pr.html_url,
          user: (pr.user as Record<string, unknown>)?.login,
          created_at: pr.created_at,
        }));
        return {
          content: [
            { type: "text" as const, text: JSON.stringify(prs, null, 2) },
          ],
        };
      }
    );
  }
}

// Worker entrypoint
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS, DELETE",
          "Access-Control-Allow-Headers": "Content-Type, Authorization, mcp-session-id",
        },
      });
    }

    const url = new URL(request.url);

    // /mcp → Durable Object にルーティング
    if (url.pathname === "/mcp" || url.pathname.startsWith("/agents/")) {
      return NotionClaudeBridge.serve("/mcp").fetch(request, env, ctx);
    }

    // Health check
    if (url.pathname === "/" && request.method === "GET") {
      return new Response(
        JSON.stringify({ status: "ok", service: "notion-claude-bridge" }),
        { headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response("Not found", { status: 404 });
  },
};
