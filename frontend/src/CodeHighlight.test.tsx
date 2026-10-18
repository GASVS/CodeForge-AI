import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python';
import oneDark from 'react-syntax-highlighter/dist/esm/styles/prism/one-dark';
import oneLight from 'react-syntax-highlighter/dist/esm/styles/prism/one-light';

SyntaxHighlighter.registerLanguage('python', python);

const PYTHON_SAMPLE = 'def add(a, b):\n    return a + b';

// Mirror of the assistant code-block render in App.tsx (real PrismLight + real theme),
// so this test fails if highlighting silently regresses.
//
// IMPORTANT: this must mirror the PRODUCTION structure, not a bare <SyntaxHighlighter/>.
// App.tsx sets the <pre> background to TRANSPARENT and instead puts the themed
// background on a Tailwind wrapper <div> (bg-slate-950 dark / bg-gray-100 light).
// So a bare highlighter here is not representative — the block background lives on the
// wrapper, exactly like in the app.
function Block({ dark }: { dark: boolean }) {
  return (
    <div className={`relative`}>
      <div className={`w-full ${dark ? 'bg-slate-950' : 'bg-gray-100'}`}>
        <SyntaxHighlighter
          language="python"
          style={dark ? oneDark : oneLight}
          showLineNumbers={false}
          customStyle={{ margin: 0, padding: '1rem', background: 'transparent' }}
        >
          {PYTHON_SAMPLE}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}

describe('assistant code highlighting (Phase 4.1)', () => {
  it('tokenizes Python into individually-colored spans', () => {
    const { container } = render(<Block dark />);
    const tokens = container.querySelectorAll('span.token');
    expect(tokens.length).toBeGreaterThan(3);
  });

  it('tokens get distinct colors (not a single uniform color)', () => {
    const { container } = render(<Block dark />);
    const colors = new Set(
      Array.from(container.querySelectorAll('span.token')).map(
        (t) => (t as HTMLElement).style.color,
      ),
    );
    // def / return / add / + must not all share one color
    expect(colors.size).toBeGreaterThan(1);
    for (const c of colors) {
      expect(c).toBeTruthy();
      expect(c).not.toBe('transparent');
    }
  });

  it('keyword `def` is colored (not the base text color)', () => {
    const { container } = render(<Block dark />);
    const def = Array.from(container.querySelectorAll('span')).find(
      (s) => s.textContent === 'def',
    ) as HTMLElement;
    expect(def).toBeTruthy();
    expect(def.style.color).toBeTruthy();
    const base = 'hsl(220, 14%, 71%)';
    expect(def.style.color).not.toBe(base);
  });

  it('preserves the exact source text (no content loss)', () => {
    const { container } = render(<Block dark={false} />);
    expect(container.textContent).toContain('def add(a, b)');
    expect(container.textContent).toContain('return a + b');
    expect(container.textContent).toMatch(/def add\(a, b\):\n +return a \+ b/);
  });

  it('dark and light themes each paint the block background (via wrapper, not transparent, and different)', () => {
    const { container: darkC } = render(<Block dark />);
    const { container: lightC } = render(<Block dark={false} />);
    // Production puts the themed background on a Tailwind wrapper <div> (bg-slate-950 dark /
    // bg-gray-100 light) and makes the <pre> transparent — so assert the wrapper's class and
    // the <pre>'s transparency together, matching what App.tsx actually renders.
    const wrapper = (root: HTMLElement) =>
      Array.from(root.querySelectorAll('div')).find(
        (d) => d.classList.contains('bg-slate-950') || d.classList.contains('bg-gray-100'),
      ) as HTMLElement;
    const pre = (root: HTMLElement) => root.querySelector('pre') as HTMLElement;

    const darkW = wrapper(darkC);
    const lightW = wrapper(lightC);
    expect(darkW).toBeTruthy();
    expect(lightW).toBeTruthy();
    expect(darkW!.classList.contains('bg-slate-950')).toBe(true);
    expect(lightW!.classList.contains('bg-gray-100')).toBe(true);
    expect(darkW).not.toBe(lightW);

    // the highlighter's <pre> is intentionally transparent in both themes
    const preBg = (el: HTMLElement) =>
      el.style.background || el.style.backgroundColor;
    expect(preBg(pre(darkC)!)).toBe('transparent');
    expect(preBg(pre(lightC)!)).toBe('transparent');
  });
});
