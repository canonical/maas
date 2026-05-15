import { readFileSync, readdirSync } from "fs";
import { dirname, join, relative, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

interface StepDefinition {
  keyword: string;
  pattern: string;
  body: string;
  normalizedBody: string;
  file: string;
  line: number;
}

// ── File discovery ────────────────────────────────────────────────────────────

function findFiles(dir: string, suffix: string): string[] {
  const results: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...findFiles(fullPath, suffix));
    } else if (entry.name.endsWith(suffix)) {
      results.push(fullPath);
    }
  }
  return results;
}

// ── Parsing helpers ───────────────────────────────────────────────────────────

/**
 * Extract the first argument of a step registration call (string or /regex/).
 * Returns the normalised pattern text and the position after the closing delimiter.
 *
 * @param content The string to be parsed
 * @param startingPosition The starting position in the string
 */
function parsePattern(
  content: string,
  startingPosition: number
): { pattern: string; endPos: number } | null {
  let position = startingPosition;
  while (position < content.length && /\s/.test(content[position])) position++;

  const character = content[position];

  if (character === '"' || character === "'") {
    const quote = character;
    position++;
    let str = "";
    while (position < content.length && content[position] !== quote) {
      if (content[position] === "\\") {
        str += content[position + 1]; // unescape
        position += 2;
      } else {
        str += content[position++];
      }
    }
    return { pattern: str, endPos: position + 1 /* skip closing quote */ };
  }

  if (character === "/") {
    position++;
    let str = "";
    while (position < content.length && content[position] !== "/") {
      if (content[position] === "\\") {
        str += `\\${content[position + 1]}`;
        position += 2;
      } else {
        str += content[position++];
      }
    }
    position++; // skip closing "/"
    while (position < content.length && /[gimsuy]/.test(content[position]))
      position++; // skip flags
    return { pattern: `/${str}/`, endPos: position };
  }

  return null;
}

/**
 * Skip a balanced parenthesised block, respecting string literals.
 * `startingIndex` must point at the opening `(`.
 * Returns the index immediately after the closing `)`, or -1 on failure.
 *
 * @param content The string to be parsed
 * @param startingIndex The starting index pointing at the opening parenthesis
 */
function skipBalancedParens(content: string, startingIndex: number): number {
  let depth = 0;
  let index = startingIndex;
  let inSingleQuote = false;
  let inDoubleQuote = false;
  let inTemplateString = false;

  while (index < content.length) {
    const character = content[index];
    if (inSingleQuote) {
      if (character === "\\") index++;
      else if (character === "'") inSingleQuote = false;
    } else if (inDoubleQuote) {
      if (character === "\\") index++;
      else if (character === '"') inDoubleQuote = false;
    } else if (inTemplateString) {
      if (character === "\\") index++;
      else if (character === "`") inTemplateString = false;
    } else {
      if (character === "'") inSingleQuote = true;
      else if (character === '"') inDoubleQuote = true;
      else if (character === "`") inTemplateString = true;
      else if (character === "(") depth++;
      else if (character === ")") {
        depth--;
        if (depth === 0) return index + 1;
      }
    }
    index++;
  }
  return -1;
}

/**
 * Extract the body of the callback that is the second argument of a step
 * registration call. Supports both arrow functions and `function` expressions
 * (the latter is used when steps need `this` context for shared state).
 *
 * @param content The string to be parsed
 * @param afterPatternPos The position after the closing delimiter of the pattern
 */
function parseCallbackBody(
  content: string,
  afterPatternPos: number
): string | null {
  let position = afterPatternPos;

  // Skip comma + whitespace between pattern and callback
  while (position < content.length && /[\s,]/.test(content[position]))
    position++;

  // ── function / async function expression ────────────────────────────────
  const isAsync = content.startsWith("async", position);
  if (isAsync) {
    position += "async".length;
    while (position < content.length && /\s/.test(content[position]))
      position++;
  }

  if (content.startsWith("function", position)) {
    position += "function".length;
    // Skip optional function name
    while (position < content.length && /\s/.test(content[position]))
      position++;
    // Skip parameter list
    if (content[position] === "(") {
      position = skipBalancedParens(content, position);
      if (position === -1) return null;
    }
    // Skip to opening brace
    while (position < content.length && content[position] !== "{") position++;
    if (position >= content.length) return null;
    return extractBraceBlock(content, position);
  }

  // ── Arrow function: (...params...) => { ... } ────────────────────────────
  // Balance the parameter list first so we don't accidentally pick up `=>`
  // from inside a regex or a later step.
  if (content[position] === "(") {
    const afterParams = skipBalancedParens(content, position);
    if (afterParams === -1) return null;
    position = afterParams;
  }

  // Skip whitespace then expect `=>`
  while (position < content.length && /[ \t]/.test(content[position]))
    position++;
  if (content[position] !== "=" || content[position + 1] !== ">") return null;
  position += 2;
  while (position < content.length && /[ \t]/.test(content[position]))
    position++;

  if (content[position] === "{") {
    return extractBraceBlock(content, position);
  }

  // Concise arrow body (single expression, no braces)
  const lineEnd = content.indexOf("\n", position);
  return content.slice(position, lineEnd !== -1 ? lineEnd : undefined).trim();
}

/**
 * Return the substring from `startingIndex` (which must point at `{`) to the
 * matching `}`, respecting string literals and nested braces.
 *
 * @param content The string to be parsed
 * @param startingIndex The starting index pointing at the opening brace
 */
function extractBraceBlock(content: string, startingIndex: number): string {
  let depth = 0;
  let index = startingIndex;
  let inSingleQuote = false;
  let inDoubleQuote = false;
  let inTemplateString = false;

  while (index < content.length) {
    const character = content[index];

    if (inSingleQuote) {
      if (character === "\\") index++;
      else if (character === "'") inSingleQuote = false;
    } else if (inDoubleQuote) {
      if (character === "\\") index++;
      else if (character === '"') inDoubleQuote = false;
    } else if (inTemplateString) {
      if (character === "\\") index++;
      else if (character === "`") inTemplateString = false;
    } else {
      if (character === "'") inSingleQuote = true;
      else if (character === '"') inDoubleQuote = true;
      else if (character === "`") inTemplateString = true;
      else if (character === "{") depth++;
      else if (character === "}") {
        depth--;
        if (depth === 0) return content.slice(startingIndex, index + 1);
      }
    }

    index++;
  }

  return content.slice(startingIndex);
}

// ── Step-definition file parser ───────────────────────────────────────────────

function normalizeBody(body: string): string {
  return body
    .replace(/\/\/[^\n]*/g, "") // strip line comments
    .replace(/\/\*[\s\S]*?\*\//g, "") // strip block comments
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Get the line number corresponding to a position in the content string.
 *
 * @param content The string content
 * @param position The position in the string
 */
function getLine(content: string, position: number): number {
  return (content.slice(0, position).match(/\n/g) ?? []).length + 1;
}

function parseStepFile(filePath: string): StepDefinition[] {
  const content = readFileSync(filePath, "utf-8");
  const defs: StepDefinition[] = [];
  const stepCallRegex = /\b(Given|When|Then)\s*\(/g;
  let match: RegExpExecArray | null;

  while ((match = stepCallRegex.exec(content)) !== null) {
    const keyword = match[1];
    const afterParen = match.index + match[0].length;

    const patternResult = parsePattern(content, afterParen);
    if (!patternResult) continue;

    const body = parseCallbackBody(content, patternResult.endPos);
    if (!body) continue;

    defs.push({
      keyword,
      pattern: patternResult.pattern,
      body,
      normalizedBody: normalizeBody(body),
      file: filePath,
      line: getLine(content, match.index),
    });
  }

  return defs;
}

// ── Reporting helpers ─────────────────────────────────────────────────────────

const rel = (p: string) => relative(ROOT, p);

const BOLD = "\x1b[1m";
const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const GREEN = "\x1b[32m";
const RESET = "\x1b[0m";
const DIM = "\x1b[2m";

function heading(text: string, color: string = RED): void {
  console.log(`\n${color}${BOLD}${text}${RESET}`);
}

function printLocation(def: StepDefinition): void {
  console.log(
    `    ${DIM}[${def.keyword}]${RESET} "${def.pattern}"`,
    `\n    ${DIM}→ ${rel(def.file)}:${def.line}${RESET}`
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

function main(): void {
  const stepDefsDir = resolve(ROOT, "cypress/support/step_definitions");
  const files = findFiles(stepDefsDir, ".steps.ts");

  if (files.length === 0) {
    console.log("No step definition files found.");
    process.exit(0);
  }

  console.log(`Scanning ${files.length} step definition file(s)…`);

  const allDefs: StepDefinition[] = files.flatMap(parseStepFile);

  console.log(`Found ${allDefs.length} step registration(s) in total.\n`);

  let issueCount = 0;

  // ── Check 1: Duplicate patterns ───────────────────────────────────────────
  {
    const patternGroups = new Map<string, StepDefinition[]>();
    for (const definition of allDefs) {
      const group = patternGroups.get(definition.pattern) ?? [];
      group.push(definition);
      patternGroups.set(definition.pattern, group);
    }

    const duplicatePatterns = [...patternGroups.values()].filter(
      (patternGroup) => patternGroup.length > 1
    );

    if (duplicatePatterns.length === 0) {
      console.log(`${GREEN}✓ No duplicate step patterns found.${RESET}`);
    } else {
      heading(
        `✗ Duplicate step patterns (${duplicatePatterns.length} pattern(s) registered more than once):`
      );
      for (const patternGroup of duplicatePatterns) {
        console.log(`\n  Pattern: "${patternGroup[0].pattern}"`);
        for (const definition of patternGroup) printLocation(definition);
        issueCount++;
      }
    }
  }

  // ── Check 2: Different patterns sharing the same implementation body ───────
  {
    const bodyGroups = new Map<string, StepDefinition[]>();
    for (const definition of allDefs) {
      const group = bodyGroups.get(definition.normalizedBody) ?? [];
      group.push(definition);
      bodyGroups.set(definition.normalizedBody, group);
    }

    // Only flag groups that contain at least two *distinct* patterns
    const clonedSteps = [...bodyGroups.values()].filter((group) => {
      const uniquePatterns = new Set(
        group.map((definition) => definition.pattern)
      );
      return uniquePatterns.size > 1;
    });

    if (clonedSteps.length === 0) {
      console.log(
        `${GREEN}✓ No different patterns sharing an identical implementation found.${RESET}`
      );
    } else {
      heading(
        `✗ Different patterns with identical implementation (${clonedSteps.length} group(s)):`,
        YELLOW
      );
      console.log(
        `${DIM}  These step patterns share the exact same callback body — they may be accidental duplicates or candidates for consolidation.${RESET}`
      );
      for (const group of clonedSteps) {
        const uniquePatterns = [
          ...new Set(
            group.map(
              (definition) => `[${definition.keyword}] "${definition.pattern}"`
            )
          ),
        ];
        console.log(`\n  Shared body:\n    ${group[0].body.trim()}`);
        console.log(`\n  Used by ${uniquePatterns.length} pattern(s):`);
        for (const definition of group) printLocation(definition);
        issueCount++;
      }
    }
  }

  // ── Summary ───────────────────────────────────────────────────────────────
  if (issueCount > 0) {
    console.log(
      `\n${RED}${BOLD}Found ${issueCount} issue(s). Review the patterns above and deduplicate where appropriate.${RESET}`
    );
    process.exit(1);
  } else {
    console.log(`\n${GREEN}${BOLD}All checks passed!${RESET}`);
    process.exit(0);
  }
}

main();
