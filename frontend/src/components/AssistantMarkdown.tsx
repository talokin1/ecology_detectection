/**
 * A tiny, safe Markdown renderer for assistant answers: paragraphs, "- " and "1. " lists, pipe
 * tables, **bold**, *italic* and [links](...). It builds React elements (never HTML strings), so
 * nothing the model writes can inject markup. Links: "#/..." becomes an in-app link; "https://"
 * opens in a new tab (the server has already kept only app pages and cited web sources).
 */
import { Fragment, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

type Block =
  | { kind: 'p'; text: string }
  | { kind: 'ul' | 'ol'; items: string[] }
  | { kind: 'table'; head: string[]; rows: string[][] };

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

function cells(line: string): string[] {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
}

export function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n?/g, '\n').split('\n');
  const out: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) out.push({ kind: 'p', text: para.join(' ') });
    para = [];
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) {
      flush();
      continue;
    }
    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1])) {
      flush();
      const head = cells(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && TABLE_ROW.test(lines[i])) rows.push(cells(lines[i++]));
      i--;
      out.push({ kind: 'table', head, rows: rows.slice(0, 12) });
      continue;
    }
    const b = BULLET.exec(line);
    const n = b ? null : NUMBERED.exec(line);
    if (b || n) {
      flush();
      const kind = b ? 'ul' : 'ol';
      const last = out[out.length - 1];
      const item = (b ?? n)![1];
      if (last && last.kind === kind) last.items.push(item);
      else out.push({ kind, items: [item] });
      continue;
    }
    const last = out[out.length - 1];
    if (!para.length && last && (last.kind === 'ul' || last.kind === 'ol') && /^\s{2,}/.test(line)) {
      last.items[last.items.length - 1] += ` ${line.trim()}`; // continuation of a list item
      continue;
    }
    para.push(line.trim());
  }
  flush();
  return out;
}

const INLINE = /(\*\*[^*\n]+\*\*|__[^_\n]+__|\[[^\]\n]{1,120}\]\([^)\s]{1,400}\)|\*[^*\n]+\*|_[^_\n]+_)/g;

export function inline(text: string, key = 'i'): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let k = 0;
  for (const m of text.matchAll(INLINE)) {
    const tok = m[0];
    if (m.index! > last) out.push(text.slice(last, m.index));
    const id = `${key}-${k++}`;
    if (tok.startsWith('**') || tok.startsWith('__')) {
      out.push(<strong key={id}>{inline(tok.slice(2, -2), id)}</strong>);
    } else if (tok.startsWith('[')) {
      const lm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok)!;
      const [label, href] = [lm[1], lm[2]];
      if (href.startsWith('#/')) out.push(<Link key={id} to={href.slice(1)}>{label}</Link>);
      else if (href.startsWith('https://')) {
        out.push(<a key={id} href={href} target="_blank" rel="noopener noreferrer">{label}</a>);
      } else out.push(label);
    } else {
      out.push(<em key={id}>{inline(tok.slice(1, -1), id)}</em>);
    }
    last = m.index! + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function AssistantMarkdown({ text }: { text: string }) {
  return (
    <div className="ai-md">
      {parseBlocks(text).map((b, i) => {
        if (b.kind === 'p') return <p key={i}>{inline(b.text, `p${i}`)}</p>;
        if (b.kind === 'table') {
          return (
            <div key={i} className="ai-md__table">
              <table>
                <thead><tr>{b.head.map((h, j) => <th key={j} scope="col">{inline(h, `h${i}${j}`)}</th>)}</tr></thead>
                <tbody>
                  {b.rows.map((r, j) => (
                    <tr key={j}>{b.head.map((_, c) => <td key={c}>{inline(r[c] ?? '', `c${i}${j}${c}`)}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        const items = b.items.map((it, j) => <li key={j}>{inline(it, `l${i}${j}`)}</li>);
        return <Fragment key={i}>{b.kind === 'ul' ? <ul>{items}</ul> : <ol>{items}</ol>}</Fragment>;
      })}
    </div>
  );
}
