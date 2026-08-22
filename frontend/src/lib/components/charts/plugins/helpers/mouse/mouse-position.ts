import type { Time } from 'lightweight-charts';

export interface MousePosition {
	x: number;
	y: number;
	time: Time | null;
	price: number | null;
	insidePlotArea: boolean;
}
