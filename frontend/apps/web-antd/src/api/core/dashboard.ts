import { requestClient } from '#/api/request';

import { getCurrentUserApi } from './auth';
import { listItemsApi } from './items';
import { listUsersApi } from './users';

export interface DashboardSummary {
  apiHealthy: boolean;
  currentUserEmail: string;
  currentUserName: string;
  isSuperuser: boolean;
  itemTotal: number;
  userTotal: null | number;
}

export function getHealthCheckApi() {
  return requestClient.get<boolean>('/utils/health-check');
}

export async function getDashboardSummaryApi(): Promise<DashboardSummary> {
  const [apiHealthy, currentUser, items] = await Promise.all([
    getHealthCheckApi(),
    getCurrentUserApi(),
    listItemsApi({ page: 1, page_size: 1 }),
  ]);

  const userTotal = currentUser.is_superuser
    ? (await listUsersApi({ page: 1, page_size: 1 })).total
    : null;

  return {
    apiHealthy,
    currentUserEmail: currentUser.email,
    currentUserName: currentUser.full_name || currentUser.email,
    isSuperuser: !!currentUser.is_superuser,
    itemTotal: items.total,
    userTotal,
  };
}
