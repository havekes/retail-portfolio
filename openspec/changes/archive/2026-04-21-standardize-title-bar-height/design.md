# Design: Standardize Title Bar Height

## Technical Approach
We will utilize Tailwind CSS classes to enforce the height constraint on the wrapper `div` of the title bar components.

### Implementation Details
The following components use a standard header wrapper:
- `AppHeader` (layout/app-header.svelte)
- `AccountsList` (accounts/accounts-list.svelte)
- `BrokersList` (brokers/brokers-list.svelte)

The wrapper `div` in these components will be updated from:
`class="flex items-center border-b px-4 py-2"`
to:
`class="flex items-center border-b px-4 py-2 h-[49px]"`

### CSS Analysis
- `h-[49px]`: Sets `height: 49px;`.
- `py-2`: Sets `padding-top: 0.5rem; padding-bottom: 0.5rem;` (8px each).
- `border-b`: Sets a 1px bottom border.
- Effective content height: `49px - (2 * 8px) - 1px = 32px`.
- `items-center`: Ensures content is vertically centered within the 32px area.

### Additional UI Adjustments
- **Skeleton Loading**: Updated `AppHeader` skeleton from a 2-row stack (`space-y-1`) to a single row (`flex items-center gap-2`) to fit the fixed 49px height without overflow.
- **Account Totals**: Reduced font size of account totals in `accounts/[id]/+page.svelte` from `text-lg` to `text-base` for a cleaner look in the standardized header.
