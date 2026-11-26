import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import App from './App';

// P2.3: streaming robustness — thinking indicator before the first token,
// Stop mid-stream keeps partial text (no frozen spinner), stream errors land
// in a card instead of hanging. EventSource is faked so no Ollama is needed;
// this pins the exact behavior the live stop-test checks.

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: ((e?: unknown) => void) | null = null;
  closed = false;
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
}

function mockFetchAll() {
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url);
    if (u.includes('/api/chats') && init?.method === 'POST') {
      return { ok: true, status: 200, json: async () => ({ id: 'c1' }) };
    }
    // Lenient default: every list-shaped endpoint answers with empty lists,
    // models carries one fake model so the send path is not gated offline.
    return {
      ok: true,
      status: 200,
      json: async () => ({ chats: [], projects: [], skills: [], logs: [], models: ['test-model'], default_model: 'test-model' }),
    };
  });
}

async function sendFirstMessage() {
  const user = userEvent.setup();
  render(<App />);
  const textarea = await screen.findByRole('textbox');
  await user.type(textarea, 'hello{Enter}');
  // sendMessage awaits chat auto-creation before opening the stream
  await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));
  return { user, es: FakeEventSource.instances[0] };
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
  vi.stubGlobal('fetch', mockFetchAll());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('P2.3 streaming robustness', () => {
  it('shows the Thinking… indicator while waiting for the first token, hides it after', async () => {
    const { es } = await sendFirstMessage();
    // No frames pushed yet → animated thinking dots + label
    expect(screen.getByText('Thinking…')).toBeInTheDocument();
    act(() => {
      es.onmessage!({ data: JSON.stringify({ type: 'text', text: 'Hi.' }) });
    });
    await waitFor(() => expect(screen.queryByText('Thinking…')).not.toBeInTheDocument());
    expect(screen.getByText(/Hi\./)).toBeInTheDocument();
  });

  it('Stop mid-stream keeps partial text, closes the stream, restores the send button', async () => {
    const { user, es } = await sendFirstMessage();
    act(() => {
      es.onmessage!({ data: JSON.stringify({ type: 'text', text: 'Partial answer' }) });
    });
    await screen.findByText(/Partial answer/);

    await user.click(screen.getByTitle('Stop generation'));

    // Partial content survives + explicit stop note; stream was closed
    expect(await screen.findByText(/Partial answer/)).toBeInTheDocument();
    expect(screen.getAllByText(/generation stopped/).length).toBeGreaterThan(0);
    expect(es.closed).toBe(true);
    // No frozen spinner: thinking indicator gone, Stop replaced by Send
    expect(screen.queryByText('Thinking…')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Stop generation')).not.toBeInTheDocument();
  });

  it('stream connection error renders an error card instead of hanging', async () => {
    const { es } = await sendFirstMessage();
    act(() => {
      es.onerror!(new Event('error'));
    });
    expect(await screen.findByText(/Lost connection/)).toBeInTheDocument();
    expect(screen.queryByText('Thinking…')).not.toBeInTheDocument();
  });
});
