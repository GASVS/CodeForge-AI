import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Jev Open Source — Privacy-First AI Coding Assistant',
  description: 'Free, local-first AI coding assistant. Alternative to Jev ($400/yr).',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
