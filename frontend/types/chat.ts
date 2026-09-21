export interface Chat {
  id: string;
  title: string;
  model?: string | null;
  created_at?: number;
  updated_at?: number;
  message_count?: number;
  messages?: { role: string; content: string }[];
}
