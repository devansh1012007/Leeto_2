/**
 * Copy catalog loader: every user-visible string comes from copy/catalog.yaml via
 * /config-time injection. Fallbacks here are only for bootstrapping before fetch.
 */
import copyYaml from "../catalog.gen.yaml?raw";

let strings: Record<string, string> = {};

export function loadCatalog(yamlText?: string): void {
  // minimal flat-YAML parser for "key: value" lines (catalog is intentionally flat)
  const source = yamlText ?? copyYaml;
  strings = {};
  for (const line of source.split("\n")) {
    const m = /^([^: ]+):\s*"(.*)"\s*$/.exec(line.trim());
    if (m) strings[m[1]] = m[2];
  }
}

export function t(key: string, params?: Record<string, string | number>): string {
  const raw = strings[key] ?? key;
  if (!params) return raw;
  return Object.entries(params).reduce((acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)), raw);
}

loadCatalog();
