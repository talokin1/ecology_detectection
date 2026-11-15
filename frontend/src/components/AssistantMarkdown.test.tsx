import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AssistantMarkdown, parseBlocks } from './AssistantMarkdown';

const md = (text: string) => render(<MemoryRouter><AssistantMarkdown text={text} /></MemoryRouter>);

describe('AssistantMarkdown', () => {
  it('parses paragraphs, lists and tables', () => {
    const b = parseBlocks('Intro line\n\n- one\n- two\n\n1. a\n2. b\n\n| A | B |\n|---|---|\n| 1 | 2 |');
    expect(b.map((x) => x.kind)).toEqual(['p', 'ul', 'ol', 'table']);
  });

  it('never renders HTML from the text', () => {
    const { container } = md('<img src=x onerror=alert(1)> **bold** <script>alert(1)</script>');
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>');
  });

  it('allows only in-app and https links', () => {
    md('[app](#/region/ukraine?var=t2m) [src](https://example.org/x) [bad](javascript:alert(1)) [rel](/etc/passwd)');
    expect(screen.getByRole('link', { name: 'app' }).getAttribute('href')).toBe('/region/ukraine?var=t2m');
    const src = screen.getByRole('link', { name: 'src' });
    expect(src.getAttribute('target')).toBe('_blank');
    expect(src.getAttribute('rel')).toContain('noopener');
    expect(screen.queryByRole('link', { name: 'bad' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'rel' })).toBeNull();
  });
});
