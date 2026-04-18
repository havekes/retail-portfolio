## 1. Database Schema

- [x] 1.1 Create price_alerts table with security_id, user_id, target_price, condition, triggered_at, created_at
- [x] 1.2 Create security_notes table with security_id, user_id, content, created_at, updated_at
- [x] 1.3 Create security_documents table with security_id, user_id, filename, file_path, file_size, file_type, created_at
- [x] 1.4 Create indicator_preferences table with security_id, user_id, indicators_json, updated_at
- [x] 1.5 Add database indexes on foreign keys (security_id, user_id) for performance
- [x] 1.6 Create database migration scripts and test on development database

## 2. Backend Models and Schemas

- [x] 2.1 Create SQLAlchemy models for PriceAlert, SecurityNote, SecurityDocument, IndicatorPreferences
- [x] 2.2 Create Pydantic schemas for request/response validation
- [x] 2.3 Create repository classes for each model with CRUD operations
- [x] 2.4 Create service classes with business logic for each feature
- [ ] 2.5 Add unit tests for models and repository operations

## 3. Backend API Endpoints - Price Alerts

- [x] 3.1 Create GET /api/securities/{security_id}/alerts endpoint to list alerts
- [x] 3.2 Create POST /api/securities/{security_id}/alerts endpoint to create alert
- [x] 3.3 Create DELETE /api/securities/{security_id}/alerts/{alert_id} endpoint to delete alert
- [x] 3.4 Add request validation and error handling
- [ ] 3.5 Add API tests for price alert endpoints

## 4. Backend API Endpoints - Security Notes

- [x] 4.1 Create GET /api/securities/{security_id}/notes endpoint to list notes
- [x] 4.2 Create POST /api/securities/{security_id}/notes endpoint to create note
- [x] 4.3 Create PUT /api/securities/{security_id}/notes/{note_id} endpoint to update note
- [x] 4.4 Create DELETE /api/securities/{security_id}/notes/{note_id} endpoint to delete note
- [ ] 4.5 Add API tests for notes endpoints

## 5. Backend API Endpoints - Security Documents

- [x] 5.1 Create GET /api/securities/{security_id}/documents endpoint to list documents
- [x] 5.2 Create POST /api/securities/{security_id}/documents endpoint to upload document
- [x] 5.3 Create GET /api/securities/{security_id}/documents/{doc_id}/download endpoint for file download
- [x] 5.4 Create DELETE /api/securities/{security_id}/documents/{doc_id} endpoint to delete document
- [x] 5.5 Implement file validation (type, size limits)
- [ ] 5.6 Add API tests for documents endpoints

## 6. Backend API Endpoints - Technical Indicators

- [x] 6.1 Implement moving average calculation functions (50-day, 200-day, 50-week, 200-week)
- [x] 6.2 Implement MACD calculation function
- [x] 6.3 Implement RSI calculation function
- [x] 6.4 Create GET /api/securities/{security_id}/indicators endpoint to get indicator data
- [x] 6.5 Create GET /api/securities/{security_id}/indicator-preferences endpoint to get saved preferences
- [x] 6.6 Create PUT /api/securities/{security_id}/indicator-preferences endpoint to save preferences
- [x] 6.7 Add caching for indicator calculations
- [ ] 6.8 Add API tests for indicators endpoints

## 7. Backend API Endpoints - AI Analysis

- [x] 7.1 Create POST /api/securities/{security_id}/ai/fundamentals endpoint for fundamentals explanation
- [x] 7.2 Create POST /api/securities/{security_id}/ai/summarize-notes endpoint for notes summary
- [x] 7.3 Create POST /api/securities/{security_id}/ai/portfolio-debate endpoint for portfolio analysis
- [x] 7.4 Implement AI service integration with context gathering (notes, portfolio, price data)
- [x] 7.5 Add timeout handling and error responses
- [ ] 7.6 Add API tests for AI endpoints

## 8. Frontend - ActionsSidebar Component

- [x] 8.1 Create ActionsSidebar base component structure in src/lib/components/actions-sidebar/
- [x] 8.2 Implement expandable/collapsible group functionality with state management
- [x] 8.3 Add group header with icon and label
- [x] 8.4 Implement action menu items with icons and hover states
- [ ] 8.5 Add responsive behavior for mobile (bottom sheet/drawer)
- [ ] 8.6 Implement keyboard navigation and accessibility (ARIA labels, focus management)
- [ ] 8.7 Add component tests for ActionsSidebar

## 9. Frontend - Technical Indicators UI

- [x] 9.1 Create IndicatorsGroup component with toggle buttons for each indicator
- [x] 9.2 Create indicators service class (indicatorsService.ts) following marketService pattern
- [x] 9.3 Update SecurityChart component to accept and display indicator overlays
- [x] 9.4 Add indicator legend to chart with color coding
- [x] 9.5 Implement indicator persistence per security (load/save preferences)
- [x] 9.6 Add loading state during indicator calculation
- [ ] 9.7 Add UI tests for indicators functionality

## 10. Frontend - Price Alerts UI

- [x] 10.1 Create AlertsGroup component with alert list and add button
- [x] 10.2 Create AlertCreationDialog component with price input and condition selector
- [x] 10.3 Create AlertListItem component with status indicators (active/triggered)
- [x] 10.4 Create alerts service class (alertsService.ts)
- [x] 10.5 Implement delete confirmation dialog
- [x] 10.6 Add empty state when no alerts exist
- [ ] 10.7 Add UI tests for alerts functionality

## 11. Frontend - Security Notes UI

- [x] 11.1 Create NotesGroup component with notes list and add button
- [x] 11.2 Create NoteCreationDialog component with text area
- [x] 11.3 Create NoteListItem component with summary and date
- [x] 11.4 Create NoteViewDialog component for full note viewing and editing
- [x] 11.5 Create notes service class (notesService.ts)
- [x] 11.6 Implement sort by date functionality
- [x] 11.7 Add empty state when no notes exist
- [ ] 11.8 Add UI tests for notes functionality

## 12. Frontend - Security Documents UI

- [x] 12.1 Create DocumentsGroup component with documents list and add button
- [x] 12.2 Create DocumentUploadDialog component with file picker and progress indicator
- [x] 12.3 Create DocumentListItem component with metadata (filename, size, date)
- [x] 12.4 Create DocumentViewDialog component for previewing documents
- [x] 12.5 Create documents service class (documentsService.ts)
- [x] 12.6 Implement file type and size validation on frontend
- [x] 12.7 Add filter/search functionality for documents
- [ ] 12.8 Add UI tests for documents functionality

## 13. Frontend - AI Analysis UI

- [x] 13.1 Create AIAnalysisGroup component with three AI action buttons
- [x] 13.2 Create AIResponseDialog component for displaying AI analysis results
- [x] 13.3 Create ai service class (aiService.ts)
- [x] 13.4 Implement loading state with estimated time during AI generation
- [x] 13.5 Add formatted response display (headings, bullets, paragraphs)
- [x] 13.6 Implement copy to clipboard functionality
- [x] 13.7 Implement save as note functionality
- [x] 13.8 Add error handling with retry option
- [ ] 13.9 Add UI tests for AI functionality

## 14. Integration - Security Page Update

- [x] 14.1 Update security/[security_id]/+page.svelte to include ActionsSidebar
- [x] 14.2 Integrate all six action groups into the sidebar
- [x] 14.3 Ensure chart and sidebar work together without layout conflicts
- [ ] 14.4 Test navigation between securities with preference persistence
- [ ] 14.5 Add loading skeleton for sidebar during initial load
- [ ] 14.6 Perform end-to-end testing of complete security page

## 15. Polish and Optimization

- [ ] 15.1 Add consistent loading states across all features
- [ ] 15.2 Implement comprehensive error handling with user-friendly messages
- [ ] 15.3 Optimize indicator calculation performance with caching
- [ ] 15.4 Test responsive design on various screen sizes
- [ ] 15.5 Perform accessibility audit and fix issues
- [ ] 15.6 Add TypeScript type definitions for all new types
- [ ] 15.7 Update documentation for new API endpoints
- [ ] 15.8 Run full test suite and fix any failures
