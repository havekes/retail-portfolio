import type { Account } from '@/types/account';
import { AccountType, Institution } from '@/types/account';

export type GroupBy = 'none' | 'institution' | 'accountType';

export type AccountGroup = {
	key: string;
	label: string;
	accounts: Account[];
};

const getInstitutionLabel = (id: Institution): string => Institution[id] ?? `Institution ${id}`;
const getAccountTypeLabel = (id: AccountType): string => AccountType[id] ?? `Account type ${id}`;

export const groupAccounts = async (
	list: Promise<Account[]>,
	groupBy: GroupBy
): Promise<AccountGroup[]> => {
	const data = await list;

	if (groupBy === 'none') {
		return [{ key: 'all', label: '', accounts: data }];
	}

	const groups = new Map<string, AccountGroup>();
	for (const account of data) {
		const key =
			groupBy === 'institution' ? String(account.institution_id) : String(account.account_type_id);
		const label =
			groupBy === 'institution'
				? getInstitutionLabel(account.institution_id)
				: getAccountTypeLabel(account.account_type_id);

		const existing = groups.get(key);
		if (existing) {
			existing.accounts.push(account);
		} else {
			groups.set(key, { key, label, accounts: [account] });
		}
	}

	return Array.from(groups.values());
};
