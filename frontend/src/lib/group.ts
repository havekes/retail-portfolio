export type GroupReturnType<T, R extends keyof T> = Promise<Map<T[R] | null, Array<T>>>;

export const group = async <T, R extends keyof T>(
	list: Promise<Array<T>>,
	groupByKey: R | null
): GroupReturnType<T, R> => {
	const data = await list;

	if (groupByKey === null) {
		return new Map([[null, data]]);
	}

	const groups = new Map<T[R], Array<T>>();

	for (const item of data) {
		const keyValue = item[groupByKey];
		const existing = groups.get(keyValue);

		if (existing) {
			existing.push(item);
		} else {
			groups.set(keyValue, [item]);
		}
	}

	return groups;
};
