import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import MessageInput from '../components/MessageInput';

describe('MessageInput', () => {
  it('renders textarea and send button', () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} disabled={false} />);
    expect(screen.getByPlaceholderText(/Type your message/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Send message/i })).toBeInTheDocument();
  });

  it('submits non-empty input on button click', async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} disabled={false} />);
    const textarea = screen.getByPlaceholderText(/Type your message/i);
    await user.type(textarea, 'hello world');
    await user.click(screen.getByRole('button', { name: /Send message/i }));
    expect(onSend).toHaveBeenCalledWith('hello world');
  });

  it('does not submit when empty/whitespace', async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const { rerender } = render(<MessageInput onSend={onSend} disabled={false} />);
    const textarea = screen.getByPlaceholderText(/Type your message/i);
    await user.type(textarea, '   ');
    await user.click(screen.getByRole('button', { name: /Send message/i }));
    expect(onSend).not.toHaveBeenCalled();
    rerender(<MessageInput onSend={onSend} disabled={false} />);
  });

  it('disables sending when disabled', async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} disabled={true} />);
    expect(screen.getByPlaceholderText(/Type your message/i)).toBeDisabled();
    expect(screen.getByRole('button', { name: /Send message/i })).toBeDisabled();
  });
});
