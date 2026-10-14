# VALARM in iCalendar

VALARM elements must appear after the `END:VEVENT` and before the closing `END:VCALENDAR`.

**Required lines**:
- `\"BEGIN:VALARM\"`
- `\"TRIGGER:-PT15M\"`
- `\"ACTION:DISPLAY\"`
- `DESCRIPTION:Reminder: Interview with ${company}`
- `\"END:VALARM\"`

**Important**: Each of these must be a separate array element when constructing the `.ics` string via `[].join("\r\n")`. If a line contains escaped newline characters (e.g., `\\n`) the resulting file will be malformed and most calendar applications will reject it.

Example fragment:
```ts
const icsContent = [
  "BEGIN:VCALENDAR",
  "BEGIN:VEVENT",
  /* event details */
  "END:VEVENT",
  "BEGIN:VALARM",
  "TRIGGER:-PT15M",
  "ACTION:DISPLAY",
  `DESCRIPTION:Reminder: Interview with ${company}`,
  "END:VALARM",
  "END:VCALENDAR"
].join("\r\n");
```
