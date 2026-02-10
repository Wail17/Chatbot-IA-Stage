# Zwembad.eu AI Chatbot Widget

Self-contained chat widget for integration on any website. Pure vanilla JavaScript, no dependencies.

## Quick Start

Add this single line before `</body>` on your website:

```html
<script src="https://chatbot-zwembad.railway.app/static/widget/widget.js"></script>
```

The chat bubble appears automatically in the bottom-right corner.

## WordPress Integration

### Option 1: Theme Footer (recommended)

1. Go to **Appearance > Theme Editor**
2. Open `footer.php`
3. Add before `</body>`:

```html
<script src="https://chatbot-zwembad.railway.app/static/widget/widget.js"></script>
```

4. Save

### Option 2: Plugin (Insert Headers and Footers)

1. Install **WPCode** or **Insert Headers and Footers** plugin
2. Go to **Settings > Insert Headers and Footers**
3. Paste in the **Footer** section:

```html
<script src="https://chatbot-zwembad.railway.app/static/widget/widget.js"></script>
```

4. Save

### Option 3: Custom HTML Block

1. Edit any page/post
2. Add a **Custom HTML** block
3. Paste:

```html
<script src="https://chatbot-zwembad.railway.app/static/widget/widget.js"></script>
```

## Features

- **Bubble toggle** — click to open/close chat window
- **Responsive** — full-screen on mobile, popup on desktop
- **Session persistence** — conversation saved in localStorage
- **Typing indicator** — animated dots while waiting for response
- **Feedback** — thumbs up/down on every bot response
- **Error handling** — friendly messages on network/timeout errors
- **Keyboard support** — Enter to send, Escape to close
- **Accessible** — ARIA labels on interactive elements
- **Zero dependencies** — pure vanilla JavaScript

## Configuration

Edit the `CONFIG` object at the top of `widget.js`:

| Key | Default | Description |
|-----|---------|-------------|
| `apiBaseUrl` | `https://chatbot-zwembad.railway.app` | Backend API URL |
| `language` | `nl` | Default language code |
| `primaryColor` | `#0066cc` | Theme color |
| `welcomeMessage` | `Hallo! Ik ben je AI assistent...` | First message shown |
| `maxStoredMessages` | `10` | Messages kept in localStorage |
| `requestTimeout` | `15000` | API timeout in milliseconds |

## API Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/chat` | Send question, receive answer |
| `POST` | `/api/feedback` | Submit thumbs up/down |

## Demo

Open `demo.html` in a browser to test the widget locally.

## Browser Support

Chrome, Firefox, Safari, Edge (all modern versions).
