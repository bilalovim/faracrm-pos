/**
 * Крошечный remark-плагин: превращает блок-цитаты вида
 *
 *   > [!info] Текст…
 *   > [!warning] Текст…
 *   > [!tip] Текст…      (маркер [!note] трактуется как info)
 *
 * в <blockquote data-kind="info|warning|tip">…</blockquote>, убирая сам маркер.
 * Атрибут data-kind ставится через data.hProperties (уважается при
 * mdast → hast), поэтому CSS-стили врезок (Docs.module.css) работают как есть.
 *
 * Плагин inline — отдельной npm-зависимости не требует. Тип дерева — any
 * (стандартная практика для unified-плагинов, чтобы не тянуть типы mdast/unist).
 */

interface MdNode {
  type: string;
  value?: string;
  children?: MdNode[];
  data?: { hProperties?: Record<string, unknown>; [k: string]: unknown };
}

const KINDS: Record<string, 'info' | 'warning' | 'tip'> = {
  info: 'info',
  warning: 'warning',
  tip: 'tip',
  note: 'info',
};

const MARKER = /^\s*\[!(info|warning|tip|note)\]\s*/i;

function applyCallout(bq: MdNode): void {
  const para = bq.children?.[0];
  if (!para || para.type !== 'paragraph' || !para.children?.length) return;

  const first = para.children[0];
  if (!first || first.type !== 'text' || typeof first.value !== 'string') return;

  const m = MARKER.exec(first.value);
  if (!m) return;

  const kind = KINDS[m[1].toLowerCase()];
  // Убираем маркер из отображаемого текста.
  first.value = first.value.slice(m[0].length);
  // Пробрасываем data-kind на итоговый <blockquote>.
  bq.data = bq.data || {};
  bq.data.hProperties = { ...(bq.data.hProperties || {}), 'data-kind': kind };
}

function walk(node: MdNode): void {
  if (!node.children) return;
  for (const child of node.children) {
    if (child.type === 'blockquote') applyCallout(child);
    walk(child);
  }
}

export function remarkCallouts() {
  return (tree: unknown): void => walk(tree as MdNode);
}

export default remarkCallouts;
