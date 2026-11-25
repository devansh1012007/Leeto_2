#!/usr/bin/env node
// T-1.6: generate a strict-mode TypeScript client from openapi/openapi.json.
// Cold-start test (A0): delete src/generated, re-run this, rebuild — tests must still pass.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const spec = JSON.parse(readFileSync(join(root, "openapi", "openapi.json"), "utf8"));

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const ident = (s) => s.replace(/[^a-zA-Z0-9]/g, "_");

// ---- schema → TS type -------------------------------------------------
function tsType(schema, defs) {
  if (!schema) return "unknown";
  if (schema.$ref) {
    const name = schema.$ref.split("/").pop();
    return `T${name}`;
  }
  if (schema.oneOf || schema.anyOf) {
    return (schema.oneOf || schema.anyOf).map((s) => tsType(s, defs)).join(" | ");
  }
  if (schema.allOf) {
    return schema.allOf.map((s) => tsType(s, defs)).join(" & ");
  }
  if (schema.enum) return schema.enum.map((v) => JSON.stringify(v)).join(" | ");
  switch (schema.type) {
    case "string":
      return schema.format === "date-time" ? "string /* RFC3339 */" : "string";
    case "number":
    case "integer":
      return "number";
    case "boolean":
      return "boolean";
    case "array":
      return `Array<${tsType(schema.items, defs)}>`;
    case "object":
    default: {
      const props = schema.properties || {};
      const req = new Set(schema.required || []);
      const lines = Object.entries(props).map(([k, v]) => {
        const opt = req.has(k) ? "" : "?";
        const nullable = v.nullable ? " | null" : "";
        const desc = v.description ? `  /** ${v.description} */\n` : "";
        return `${desc}  ${JSON.stringify(k)}${opt}: ${tsType(v, defs)}${nullable};`;
      });
      if (schema.additionalProperties === false || lines.length === 0) {
        return `{\n${lines.join("\n")}\n}`;
      }
      return `{\n${lines.join("\n")}\n  [k: string]: unknown;\n}`;
    }
  }
}

// ---- component schemas -------------------------------------------------
const defs = spec.components.schemas;
const schemaOut = Object.entries(defs)
  .map(([name, sch]) => {
    const desc = sch.description ? `/** ${sch.description} */\n` : "";
    return `${desc}export type T${name} = ${tsType(sch, defs)};\n`;
  })
  .join("\n");

// ---- operations --------------------------------------------------------
const ops = [];
for (const [path, item] of Object.entries(spec.paths)) {
  for (const [method, op] of Object.entries(item)) {
    if (!["get", "post", "put", "delete", "patch"].includes(method)) continue;
    const fn = `${method}${ident(path)}`;
    const bodySchema = op.requestBody?.content?.["application/json"]?.schema;
    const params = [];
    for (const p of op.parameters || []) {
      if (p.in === "path") params.push({ name: ident(p.name), ts: tsType(p.schema, defs), in: "path", raw: p.name });
      if (p.in === "query") params.push({ name: ident(p.name), ts: tsType(p.schema, defs) + " | undefined", in: "query", raw: p.name });
      if (p.in === "header") params.push({ name: ident(p.name), ts: tsType(p.schema, defs) + " | undefined", in: "header", raw: p.name });
    }
    ops.push({ fn, method, path, op, bodySchema, params });
  }
}

function renderClientFns(opList) {
  return opList
  .map(({ fn, method, path, op, bodySchema, params }) => {
    const args = [];
    for (const p of params) args.push(`${p.name}: ${p.ts}`);
    if (bodySchema) args.push(`body: ${tsType(bodySchema, defs)}`);
    args.push(`opts?: RequestOpts`);
    const seg = path
      .split("/")
      .map((s) => (s.startsWith("{") ? `\${${ident(s.slice(1, -1))}}` : s))
      .join("/");
    const queryNames = params.filter((p) => p.in === "query").map((p) => p.name);
    const headerParams = params.filter((p) => p.in === "header");
    const q = queryNames.length
      ? `const qs = new URLSearchParams();\n    ${queryNames.map((n) => `if (${n} !== undefined) qs.set("${n}", String(${n}));`).join("\n    ")}\n    url += "?" + qs.toString();\n    `
      : "";
    const h = headerParams.length
      ? `headers: { ...optHeaders, ${headerParams.map((p) => `${JSON.stringify(p.raw)}: String(${p.name})`).join(", ")} },\n      `
      : "";
    return `  /** ${op.summary} */
  async ${fn}(${args.join(", ")}): Promise<unknown> {
    let url = \`${seg}\`;
    ${q}
    const optHeaders = (opts && opts.headers) || {};
    return this.request(url, {
      ...opts,
      method: "${method.toUpperCase()}",
      ${h}${bodySchema ? "body,\n      " : ""}});
  }`;
  })
  .join("\n\n");
}

function renderClientSource(fns, className, headerNote) {
  return `// GENERATED from openapi/openapi.json — ${headerNote}
// Regenerate: pnpm --filter api-client gen
export interface RequestOpts {
  fetchImpl?: typeof fetch;
  baseUrl?: string;
  token?: string;
  headers?: Record<string, string>;
}

${schemaOut}

export class ${className} {
  private base: string;
  private fetchImpl: typeof fetch;
  private token?: string;
  private extraHeaders: Record<string, string>;

  constructor(opts: RequestOpts = {}) {
    this.base = (opts.baseUrl || "").replace(/\\/$/, "");
    this.fetchImpl = opts.fetchImpl || globalThis.fetch.bind(globalThis);
    this.token = opts.token;
    this.extraHeaders = opts.headers || {};
  }

  setToken(token: string | undefined): void {
    this.token = token;
  }

  private async request(path: string, init: { method: string; body?: unknown; headers?: Record<string, string> }): Promise<unknown> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Client-Version": "1.0.0",
      ...this.extraHeaders,
      ...(init.headers || {}),
    };
    if (this.token) headers["Authorization"] = \`Bearer \${this.token}\`;
    const res = await this.fetchImpl(this.base + path, {
      method: init.method,
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
    if (res.status === 304) return null;
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const err = (json && (json as { error?: { code?: string } }).error) || {};
      throw new ApiError(err.code || "INTERNAL", err.message || res.statusText, res.status);
    }
    return json;
  }

${fns}
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  constructor(code: string, message: string, status: number) {
    super(\`[\${code}] \${message}\`);
    this.code = code;
    this.status = status;
  }
}
`;
}

const out = renderClientSource(renderClientFns(ops), "ApiClient", "do not edit by hand.");

const outDir = join(root, "frontend", "packages", "api-client", "src", "generated");
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, "client.ts"), out);

// ---- participant-scoped client (bundle-check gate: no admin/runner ops in the
// participant bundle, R-34) --------------------------------------------------
const participantOps = ops.filter(({ path }) =>
  !path.startsWith("/v1/admin") && !path.startsWith("/runner/") && path !== "/metrics");
const participantOut = renderClientSource(renderClientFns(participantOps), "ParticipantClient",
  "PARTICIPANT-SCOPED (no admin/runner ops).");
writeFileSync(join(outDir, "participant.ts"), participantOut);

writeFileSync(
  join(outDir, "index.ts"),
  `export * from "./client.js";\nexport { ParticipantClient } from "./participant.js";\n`,
);
console.log(`generated ${ops.length} operations (client.ts) + ${participantOps.length} participant ops (participant.ts)`);
