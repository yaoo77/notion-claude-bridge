/**
 * Notion AI → GitHub Bridge MCP Server
 * Cloudflare Worker として動作し、Notion AI のカスタムエージェントから
 * GitHub Issue 作成・PR コメントを行う
 */

interface Env {
  GITHUB_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  MCP_AUTH_TOKEN: string;
}

// MCP Protocol types
interface MCPRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: string;
  params?: Record<string, unknown>;
}

interface MCPResponse {
  jsonrpc: "2.0";
  id: string | number;
  result?: unknown;
  error?: { code: number; message: string };
}

// Tool definitions
const TOOLS = [
  {
    name: "create_issue",
    description:
      "GitHub Issueを作成し、Claude Code（GitHub Actions）を起動します。Issueのタイトルと本文を指定してください。本文に実装指示を書くと、Claude Codeが自動でPRを作成します。",
    inputSchema: {
      type: "object" as const,
      properties: {
        title: {
          type: "string",
          description: "Issueのタイトル",
        },
        body: {
          type: "string",
          description:
            "Issueの本文。Claude Codeへの実装指示を含めてください。",
        },
        labels: {
          type: "array",
          items: { type: "string" },
          description: "ラベル（省略可）",
        },
      },
      required: ["title", "body"],
    },
  },
  {
    name: "comment_on_issue",
    description:
      "既存のIssueまたはPRにコメントを投稿します。@claudeを含めるとClaude Codeが反応して追加作業を行います。",
    inputSchema: {
      type: "object" as const,
      properties: {
        issue_number: {
          type: "number",
          description: "IssueまたはPRの番号",
        },
        body: {
          type: "string",
          description:
            "コメント本文。Claude Codeに指示する場合は @claude を含めてください。",
        },
      },
      required: ["issue_number", "body"],
    },
  },
  {
    name: "list_pull_requests",
    description:
      "リポジトリのPR一覧を取得します。Claude Codeが作成したPRの状況確認に使います。",
    inputSchema: {
      type: "object" as const,
      properties: {
        state: {
          type: "string",
          enum: ["open", "closed", "all"],
          description: "PRの状態（デフォルト: open）",
        },
      },
    },
  },
];

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

async function handleToolCall(
  env: Env,
  name: string,
  args: Record<string, unknown>
): Promise<unknown> {
  switch (name) {
    case "create_issue": {
      const res = await githubAPI(env, "/issues", "POST", {
        title: args.title,
        body: args.body,
        labels: args.labels || [],
      });
      const data = (await res.json()) as Record<string, unknown>;
      if (!res.ok) throw new Error(`GitHub API error: ${JSON.stringify(data)}`);
      return {
        issue_number: data.number,
        url: data.html_url,
        message: `Issue #${data.number} を作成しました。Claude Codeが自動で処理を開始します。`,
      };
    }

    case "comment_on_issue": {
      const res = await githubAPI(
        env,
        `/issues/${args.issue_number}/comments`,
        "POST",
        { body: args.body }
      );
      const data = (await res.json()) as Record<string, unknown>;
      if (!res.ok) throw new Error(`GitHub API error: ${JSON.stringify(data)}`);
      return {
        comment_url: data.html_url,
        message: `Issue/PR #${args.issue_number} にコメントしました。`,
      };
    }

    case "list_pull_requests": {
      const state = (args.state as string) || "open";
      const res = await githubAPI(env, `/pulls?state=${state}`);
      const data = (await res.json()) as Array<Record<string, unknown>>;
      if (!res.ok) throw new Error(`GitHub API error: ${JSON.stringify(data)}`);
      return data.map((pr) => ({
        number: pr.number,
        title: pr.title,
        state: pr.state,
        url: pr.html_url,
        user: (pr.user as Record<string, unknown>)?.login,
        created_at: pr.created_at,
      }));
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

function mcpResponse(id: string | number, result: unknown): MCPResponse {
  return { jsonrpc: "2.0", id, result };
}

function mcpError(
  id: string | number,
  code: number,
  message: string
): MCPResponse {
  return { jsonrpc: "2.0", id, error: { code, message } };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // CORS
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
      });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    // Bearer token認証
    const authHeader = request.headers.get("Authorization");
    if (!authHeader || authHeader !== `Bearer ${env.MCP_AUTH_TOKEN}`) {
      return new Response("Unauthorized", { status: 401 });
    }

    const body = (await request.json()) as MCPRequest;
    let response: MCPResponse;

    switch (body.method) {
      case "initialize":
        response = mcpResponse(body.id, {
          protocolVersion: "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: {
            name: "notion-claude-bridge",
            version: "1.0.0",
          },
        });
        break;

      case "tools/list":
        response = mcpResponse(body.id, { tools: TOOLS });
        break;

      case "tools/call": {
        const params = body.params as {
          name: string;
          arguments: Record<string, unknown>;
        };
        try {
          const result = await handleToolCall(
            env,
            params.name,
            params.arguments || {}
          );
          response = mcpResponse(body.id, {
            content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
          });
        } catch (e) {
          const msg = e instanceof Error ? e.message : String(e);
          response = mcpResponse(body.id, {
            content: [{ type: "text", text: `Error: ${msg}` }],
            isError: true,
          });
        }
        break;
      }

      default:
        response = mcpError(body.id, -32601, `Method not found: ${body.method}`);
    }

    return new Response(JSON.stringify(response), {
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });
  },
};
