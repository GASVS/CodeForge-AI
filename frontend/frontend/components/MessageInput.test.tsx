import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import MessageInput from '../components/MessageInput'

test('renders textarea and button', () => {
  const onSend = jest.fn()
  render(<MessageInput onSend={onSend} disabled={false} />)
  const textarea = screen.getByPlaceholderText(/Type your message/i)
  expect(textarea).toBeInTheDocument()
  const button = screen.getByRole('button', { name: /Send message/i })
  expect(button).toBeInTheDocument()
  fireEvent.change(textarea, { target: { value: 'hi' } })
  fireEvent.click(button)
  expect(onSend).toHaveBeenCalledWith('hi')
})
