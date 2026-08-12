import { TickMarkType, type Time } from 'lightweight-charts';

export function formatDateToISO(date: Date): string {
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
}

export function getDateRange(daysBack: number): { from: string; to: string } {
	const today = new Date();
	const past = new Date(today);
	past.setDate(today.getDate() - daysBack);
	return {
		from: formatDateToISO(past),
		to: formatDateToISO(today)
	};
}

export function formatDate(dateString: string | Date): string {
	const date = typeof dateString === 'string' ? new Date(dateString) : dateString;
	return date.toLocaleDateString('en-US', {
		month: 'short',
		day: 'numeric',
		year: 'numeric'
	});
}

export function getChartDateWindow(endDate: Date, interval: string): { from: string; to: string } {
	const isIntraday = interval === '1h' || interval === '4h';
	const fromDate = new Date(endDate);

	if (isIntraday) {
		fromDate.setDate(fromDate.getDate() - 30);
	} else {
		fromDate.setFullYear(fromDate.getFullYear() - 2);
	}

	return {
		from: formatDateToISO(fromDate),
		to: formatDateToISO(endDate)
	};
}

export function formatLocalTime(time: Time): string {
	if (typeof time !== 'number') {
		return typeof time === 'string' ? time : JSON.stringify(time);
	}

	const date = new Date(time * 1000);
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	const hours = String(date.getHours()).padStart(2, '0');
	const minutes = String(date.getMinutes()).padStart(2, '0');

	return `${year}-${month}-${day} ${hours}:${minutes}`;
}

export function formatLocalTickMark(
	time: Time,
	tickMarkType: TickMarkType,
	locale: string
): string | null {
	if (typeof time !== 'number') {
		return null;
	}

	const date = new Date(time * 1000);

	switch (tickMarkType) {
		case TickMarkType.Year:
			return date.toLocaleDateString(locale, { year: 'numeric' });
		case TickMarkType.Month:
			return date.toLocaleDateString(locale, { month: 'short' });
		case TickMarkType.DayOfMonth:
			return date.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
		case TickMarkType.Time:
			return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
		case TickMarkType.TimeWithSeconds:
			return date.toLocaleTimeString(locale, {
				hour: '2-digit',
				minute: '2-digit',
				second: '2-digit'
			});
		default:
			return date.toLocaleString(locale);
	}
}
