/**
 * RFC 6902 JSON Patch Engine for Zustand & Master Manifest (TASK-4.4).
 */

export interface PatchOperation {
  op: 'add' | 'remove' | 'replace' | 'move' | 'copy' | 'test';
  path: string;
  value?: any;
  from?: string;
}

export interface PatchDeltaEvent {
  type: 'patch';
  projectId: string;
  version: number;
  patches: PatchOperation[];
}

/**
 * Parse JSON pointer string into tokens.
 */
function parseJsonPointer(path: string): (string | number)[] {
  if (!path || path === '/') return [];
  return path
    .replace(/^\//, '')
    .split('/')
    .map((token) => {
      const decoded = token.replace(/~1/g, '/').replace(/~0/g, '~');
      return /^\d+$/.test(decoded) ? parseInt(decoded, 10) : decoded;
    });
}

/**
 * Apply a sequence of RFC 6902 patch operations to a document immutably.
 */
export function applyJsonPatches<T extends Record<string, any>>(
  document: T,
  patches: PatchOperation[]
): T {
  // Deep clone to ensure immutability
  const clone = JSON.parse(JSON.stringify(document)) as T;

  for (const patch of patches) {
    const { op, path, value } = patch;
    if (!path) continue;

    if (path === '/') {
      if (op === 'replace' && typeof value === 'object') {
        return JSON.parse(JSON.stringify(value));
      }
      continue;
    }

    const tokens = parseJsonPointer(path);
    if (tokens.length === 0) continue;

    let current: any = clone;
    for (let i = 0; i < tokens.length - 1; i++) {
      const token = tokens[i];
      if (Array.isArray(current)) {
        current = current[token as number];
      } else if (current && typeof current === 'object') {
        if (!(token in current)) {
          current[token] = typeof tokens[i + 1] === 'number' ? [] : {};
        }
        current = current[token];
      }
    }

    const lastToken = tokens[tokens.length - 1];

    if (op === 'replace' || op === 'add') {
      if (Array.isArray(current)) {
        if (typeof lastToken === 'number') {
          if (op === 'add') {
            current.splice(lastToken, 0, value);
          } else {
            current[lastToken] = value;
          }
        } else if (lastToken === '-') {
          current.push(value);
        }
      } else if (current && typeof current === 'object') {
        current[lastToken] = value;
      }
    } else if (op === 'remove') {
      if (Array.isArray(current) && typeof lastToken === 'number') {
        current.splice(lastToken, 1);
      } else if (current && typeof current === 'object') {
        delete current[lastToken];
      }
    }
  }

  return clone;
}
