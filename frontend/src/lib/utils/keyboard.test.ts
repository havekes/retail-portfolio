import { describe, it, expect, afterEach } from 'vitest';
import { isTypingTarget } from './keyboard';

describe('isTypingTarget', () => {
	const attached: HTMLElement[] = [];

	function attach(element: HTMLElement): HTMLElement {
		document.body.appendChild(element);
		attached.push(element);
		return element;
	}

	afterEach(() => {
		for (const element of attached) element.remove();
		attached.length = 0;
	});

	it('returns false for null and non-HTMLElement targets', () => {
		expect(isTypingTarget(null)).toBe(false);
		expect(isTypingTarget(window)).toBe(false);
		expect(isTypingTarget(document)).toBe(false);
		expect(isTypingTarget(new EventTarget())).toBe(false);
	});

	it('returns true for input, textarea and select elements', () => {
		expect(isTypingTarget(attach(document.createElement('input')))).toBe(true);
		expect(isTypingTarget(attach(document.createElement('textarea')))).toBe(true);
		expect(isTypingTarget(attach(document.createElement('select')))).toBe(true);
	});

	it('returns true for a contenteditable host even where the property is missing', () => {
		const editable = attach(document.createElement('div'));
		editable.setAttribute('contenteditable', 'true');

		// jsdom does not implement `isContentEditable`, so this exercises the
		// attribute fallback the guard relies on in browsers and tests alike.
		expect(editable.isContentEditable).toBeFalsy();
		expect(isTypingTarget(editable)).toBe(true);
	});

	it('returns true for the empty-string contenteditable form', () => {
		const editable = attach(document.createElement('div'));
		editable.setAttribute('contenteditable', '');

		expect(isTypingTarget(editable)).toBe(true);
	});

	it('returns true for a descendant of a typing surface', () => {
		const editable = attach(document.createElement('div'));
		editable.setAttribute('contenteditable', 'true');
		const child = editable.appendChild(document.createElement('span'));
		const label = attach(document.createElement('label'));
		const labelChild = label.appendChild(document.createElement('span'));

		expect(isTypingTarget(child)).toBe(true);
		// A non-editable child of a non-editable host is not a typing surface.
		expect(isTypingTarget(labelChild)).toBe(false);
	});

	it('returns false for clickable non-typing surfaces', () => {
		expect(isTypingTarget(attach(document.createElement('button')))).toBe(false);
		expect(isTypingTarget(attach(document.createElement('div')))).toBe(false);
		expect(isTypingTarget(attach(document.createElement('a')))).toBe(false);
	});
});
