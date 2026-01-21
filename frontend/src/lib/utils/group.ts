import type { Account } from '@/types/account';

type GroupBy = 'none' | 'institution' | 'accountType';

interface GroupedAccounts<T = string> {
	key: T;
	label: string;
	accounts: Account[];
}

export const groupAccounts = async (
	listPromise: Promise<Account[]>,
	groupBy: GroupBy,
	labelMap: Record<string, string>
): Promise<GroupedAccounts[]> => {
	const accounts = await listPromise;

	if (groupBy === 'none') {
		return [{ key: 'all', label: '', accounts }];
	}

	const groups: Record<string, GroupedAccounts> = {};

	for (const account of accounts) {
		const key =
			groupBy === 'institution' ? String(account.institution_id) : String(account.account_type_id);
		const label = labelMap[key] ?? 'Unknown';

		if (groups[key]) {
			groups[key].accounts.push(account);
		} else {
			groups[key] = { key, label, accounts: [account] };
		}
	}

	return Object.values(groups);
};
