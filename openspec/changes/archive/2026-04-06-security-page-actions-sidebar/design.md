## Context

The retail-portfolio application uses SvelteKit (Svelte 5) with TypeScript on the frontend and FastAPI with PostgreSQL on the backend. The existing sidebar infrastructure uses shadcn-svelte components. The security detail page currently displays only a chart and basic security information.

This change introduces a comprehensive actions sidebar with six new capabilities: reusable sidebar component, technical indicators, price alerts, security notes, security documents, and AI-powered analysis features.

## Goals / Non-Goals

**Goals:**
- Create a reusable ActionsSidebar component following existing shadcn-svelte patterns
- Implement six distinct action groups with expandable/collapsible behavior
- Add technical indicator overlays to the existing chart component
- Build CRUD operations for price alerts, notes, and documents
- Integrate AI analysis features with proper loading states and error handling
- Persist user preferences per security (indicators, notes, alerts, documents)

**Non-Goals:**
- AI model selection or implementation details (assumes AI service exists)
- Real-time price alert checking infrastructure (assumes notification system)
- Document storage infrastructure (assumes file storage exists)
- Advanced technical indicators beyond the specified set
- Social sharing or collaboration features

## Decisions

### Decision 1: Reuse existing Sidebar component infrastructure

**Choice:** Extend the existing `ui/sidebar` component system rather than creating a new sidebar implementation.

**Rationale:** The project already has a comprehensive sidebar component system from shadcn-svelte with Header, Content, Footer, Group, Menu, and MenuItem primitives. Reusing this ensures consistency with the existing app sidebar and reduces code duplication.

**Alternatives considered:**
- Building a custom sidebar from scratch: Would duplicate effort and create inconsistency
- Using a different UI library: Would introduce new dependencies and styling conflicts

### Decision 2: Separate service layer for each capability

**Choice:** Create distinct service classes (`alertsService`, `notesService`, `documentsService`, `indicatorsService`, `aiService`) following the existing `marketService` pattern.

**Rationale:** The project uses a clear separation between UI components (`.svelte`), service layer (`.ts` with `$state`), and API layer (`.ts` raw HTTP). This pattern promotes testability and maintainability.

**Alternatives considered:**
- Single monolithic service: Would violate single responsibility principle
- Direct API calls from components: Would duplicate logic and make testing difficult

### Decision 3: Indicator calculations on backend

**Choice:** Calculate technical indicators server-side in FastAPI and return pre-computed values to frontend.

**Rationale:** Indicator calculations can be computationally expensive for large datasets. Server-side calculation allows for optimization, caching, and consistent results across clients.

**Alternatives considered:**
- Client-side calculation: Would consume user device resources and potentially cause lag
- Third-party indicator service: Would add external dependency and latency

### Decision 4: Per-security preference storage

**Choice:** Store indicator preferences, alerts, notes, and documents with foreign key to security table.

**Rationale:** Users expect their research and configurations to persist per security. This enables returning to a security and having all their work available.

**Alternatives considered:**
- Session-only storage: Would lose user work on navigation
- Global preferences only: Would not support per-security customization

### Decision 5: Dialog-based action flows

**Choice:** Use modal dialogs for add/edit flows (alerts, notes, documents, AI responses).

**Rationale:** Dialogs provide focused interaction without navigating away from the security page. The existing `ui/dialog` component from shadcn-svelte can be reused.

**Alternatives considered:**
- Separate pages for each action: Would require navigation and lose context
- Inline expansion only: Would clutter the sidebar and reduce available space

## Risks / Trade-offs

**Risk:** AI features may have latency or fail, degrading user experience.

→ Mitigation: Implement clear loading states, reasonable timeouts, graceful error messages, and retry options. Cache AI responses where appropriate.

**Risk:** Technical indicator calculations may be slow for securities with extensive history.

→ Mitigation: Implement server-side caching, limit historical data range, use database indexes, and provide loading feedback.

**Risk:** Document storage may consume significant space over time.

→ Mitigation: Enforce file size limits (10MB), implement storage quotas per user, and provide cleanup tools.

**Risk:** Actions sidebar may clutter the UI on smaller screens.

→ Mitigation: Implement responsive design with bottom sheet on mobile, ensure proper touch targets, and allow sidebar collapse.

**Trade-off:** Building six capabilities simultaneously increases initial development time.

→ Benefit: All features are delivered together with consistent UX patterns, reducing long-term technical debt.

## Migration Plan

### Phase 1: Infrastructure (Days 1-2)
1. Create ActionsSidebar component structure
2. Set up database migrations for new tables
3. Create backend service skeletons and API endpoints

### Phase 2: Core Features (Days 3-5)
1. Implement technical indicators (calculations + UI)
2. Implement price alerts (CRUD + UI)
3. Implement security notes (CRUD + UI)

### Phase 3: Advanced Features (Days 6-7)
1. Implement security documents (upload + UI)
2. Implement AI analysis features
3. Integrate all features into ActionsSidebar

### Phase 4: Polish (Days 8-9)
1. Add loading states and error handling
2. Implement per-security preference persistence
3. Responsive design and accessibility testing
4. Performance optimization

### Rollback Strategy
- Database migrations are additive only (no destructive changes)
- Feature flags can disable new functionality without code deployment
- Security page reverts to original state if sidebar is disabled

## Open Questions

1. **AI service provider:** Which AI service will be used (OpenAI, Anthropic, local model)? This affects API integration and cost considerations.

2. **Price alert notification mechanism:** How should triggered alerts be delivered (in-app only, email, push notifications)? This affects backend infrastructure requirements.

3. **Document storage solution:** Where will uploaded documents be stored (S3, local filesystem, cloud storage)? This affects file handling implementation.

4. **Indicator defaults:** Should users have global default indicators that apply to all securities, or should each security start with no indicators?

5. **Notes rich text:** Should notes support rich text formatting or plain text only? This affects the text editor component choice.
