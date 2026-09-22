/**
 * True when a keyboard event is aimed at a typing surface, i.e. the handler must
 * ignore single-key shortcuts so typing is never hijacked.
 *
 * Covers `<input>`, `<textarea>`, `<select>` and `contenteditable` hosts (or any
 * descendant of one). Shared by the root-layout shortcuts, the notes `n`
 * shortcut, and the chart drawing shortcuts so all three agree on what counts as
 * a typing surface.
 */
export function isTypingTarget(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) return false;
	return (
		target.tagName === 'INPUT' ||
		target.tagName === 'TEXTAREA' ||
		target.tagName === 'SELECT' ||
		target.isContentEditable ||
		// jsdom does not implement `isContentEditable`, so also match the
		// attribute directly (and catch descendants of a contenteditable host).
		target.closest('[contenteditable="true"], [contenteditable=""]') !== null
	);
}
