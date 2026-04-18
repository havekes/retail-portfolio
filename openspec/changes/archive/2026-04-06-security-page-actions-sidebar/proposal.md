## Why

The security detail page needs an actions sidebar to provide quick access to analytical tools, AI insights, and personal research features. Currently, users have no centralized way to access indicators, set price alerts, manage notes, or leverage AI analysis for individual securities.

## What Changes

- Add a new left sidebar component to the security detail page with grouped actions
- Create reusable `ActionsSidebar` component with expandable action groups
- Add technical indicators section (50/200 day MA, 50/200 week MA, MACD, RSI, more)
- Add AI-powered actions (explain fundamentals, summarize notes, portfolio debate)
- Add price alerts management (add alert, list existing alerts)
- Add notes management (add note, list existing notes with summaries)
- Add documents management (add document, list existing documents)

## Capabilities

### New Capabilities

- `actions-sidebar`: Reusable sidebar component for grouped, expandable actions with consistent UI patterns
- `technical-indicators`: Configuration and display of technical analysis indicators on security charts
- `price-alerts`: Create, manage, and display price alert notifications for securities
- `security-notes`: Add, edit, and retrieve user notes for individual securities
- `security-documents`: Upload, store, and retrieve documents associated with securities
- `ai-security-analysis`: AI-powered analysis features including fundamentals explanation, notes summarization, and portfolio recommendation debate

### Modified Capabilities

- None

## Impact

**Frontend:**
- New `ActionsSidebar` component in `src/lib/components/`
- Modified `security/[security_id]/+page.svelte` to include actions sidebar
- New service layer for indicators, alerts, notes, documents, and AI features
- New UI components for each action group (dialogs, lists, forms)

**Backend:**
- New API endpoints for price alerts CRUD
- New API endpoints for security notes CRUD
- New API endpoints for security documents CRUD
- New API endpoints for technical indicator calculations
- New API endpoints for AI analysis features

**Database:**
- New tables: `price_alerts`, `security_notes`, `security_documents`
- Foreign key relationships to `security` table
