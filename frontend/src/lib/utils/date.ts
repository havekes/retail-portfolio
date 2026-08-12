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

export function getChartDateWindow(
	endDate: Date,
	interval: string
): { from: string; to: string } {
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

