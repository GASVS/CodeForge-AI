import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { CodeNavPanel } from './ProjectPanel';

// P6.2: code-navigation panel — symbol search, outline jump-to-line, refs.

const files = [{ id: 'f1', path: 'demo/main.py', size: 100, line_count: 3 }];

function mockFetch(routes: Array<[RegExp, unknown]>) {
  return vi.fn(async (url: RequestInfo | URL) => {
    for (const [re, body] of routes) {
      if (re.test(String(url))) {
        return { ok: true, status: 200, json: async () => body };
      }
    }
    return { ok: false, status: 404, json: async () => ({ detail: 'not mocked' }) };
  });
}

function renderPanel(outlineFor: string | null = null) {
  return render(
    <CodeNavPanel
      apiUrl="http://api"
      projectId="p1"
      projectName="demo-proj"
      theme="dark"
      files={files}
      outlineFor={outlineFor}
      setOutlineFor={() => {}}
    />,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('CodeNavPanel (P6.2)', () => {
  it('searches symbols and shows file:line for each hit', async () => {
    vi.stubGlobal('fetch', mockFetch([
      [/\/symbols\?q=/, {
        symbols: [{ name: 'load_config', kind: 'function', sig: 'def load_config()', file_ref: 'demo/main.py', start_line: 7, end_line: 12 }],
      }],
    ]));
    renderPanel();
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/Find a symbol/i), 'load_config');
    await user.click(screen.getByRole('button', { name: 'Go' }));
    await waitFor(() => expect(screen.getByText('load_config')).toBeInTheDocument());
    expect(screen.getByText('demo/main.py:7')).toBeInTheDocument();
  });

  it('shows the outline for a selected file and jumps to the symbol line', async () => {
    const content = Array.from({ length: 25 }, (_, i) => `line ${i + 1}`).join('\n');
    vi.stubGlobal('fetch', mockFetch([
      [/\/outline\?path=/, {
        path: 'demo/main.py',
        symbols: [{ name: 'main', kind: 'function', sig: 'def main()', file_ref: 'demo/main.py', start_line: 20, end_line: 25 }],
      }],
      [/\/files\/f1$/, { id: 'f1', project_id: 'p1', path: 'demo/main.py', content, line_count: 25 }],
    ]));
    renderPanel('demo/main.py');
    await waitFor(() => expect(screen.getByRole('button', { name: /main/ })).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /main/ }));
    await waitFor(() => expect(screen.getByTestId('code-line-20')).toBeInTheDocument());
    expect(screen.getByTestId('code-line-20')).toHaveTextContent('line 20');
    expect((screen.getByTestId('code-line-20') as HTMLElement).className).toContain('bg-indigo-500/20');
    // breadcrumb shows project › path › symbol (project name appears in both headers)
    expect(screen.getAllByText('demo-proj').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(':20')).toBeInTheDocument();
  });

  it('expands definitions and references for a search hit', async () => {
    vi.stubGlobal('fetch', mockFetch([
      [/\/symbols\?q=/, {
        symbols: [{ name: 'load_config', kind: 'function', sig: '', file_ref: 'demo/main.py', start_line: 7, end_line: 12 }],
      }],
      [/\/references$/, {
        name: 'load_config',
        definitions: [{ file_ref: 'demo/util.py', kind: 'function', start_line: 3 }],
        references: [{ from_file: 'demo/main.py', from_symbol: 'cli', kind: 'call', line: 42 }],
      }],
    ]));
    renderPanel();
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/Find a symbol/i), 'load_config');
    await user.click(screen.getByRole('button', { name: 'Go' }));
    await waitFor(() => expect(screen.getByText('load_config')).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'Refs' }));
    await waitFor(() => expect(screen.getByText('demo/util.py:3')).toBeInTheDocument());
    expect(screen.getByText('demo/main.py:42')).toBeInTheDocument();
  });

  it('re-indexes symbols and reports the counts', async () => {
    vi.stubGlobal('fetch', mockFetch([
      [/\/index-symbols$/, { files_indexed: 2, symbols: 9, references: 14 }],
    ]));
    renderPanel();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Index symbols/ }));
    await waitFor(() => expect(screen.getByText(/Indexed 9 symbols \/ 14 references in 2 files/)).toBeInTheDocument());
  });
});
