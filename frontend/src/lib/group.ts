import type { Account } from '@/types/account';

export type GroupBy = 'none' | 'institution' | 'accountType';

export type AccountGroup = {
	key: string;
	label: string;
	accounts: Account[];
};

export type GroupReturnType<T> = Promise<Map<any, Array<T>>>;

export const group = async <T, R extends keyof T>(
	list: Promise<Array<T>>,
	groupByKey: R | null
): GroupReturnType<T> => {
	const data = await list;

	if (groupByKey === null) {
		return new Map<null, Array<T>>([[null, data]]);
	}

	const groups = new Map<any, Array<T>>();

	for (const item of data) {
		const keyValue = item[groupByKey];

		const existing = groups.get(keyValue);

		if (existing) {
			existing.push(item);
			groups.set(keyValue, existing);
		} else {
			groups.set(keyValue, [item]);
		}
	}

	return groups;
};
