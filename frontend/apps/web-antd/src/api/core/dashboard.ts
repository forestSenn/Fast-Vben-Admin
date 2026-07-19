import { requestClient } from '#/api/request';

import { getCurrentUserApi } from './auth';
import { listUsersApi } from './users';

export interface DashboardOverview {
  file_count: number;
  file_total: number;
  login_count: number;
  login_total: number;
  operation_count: number;
  operation_total: number;
  user_count: number;
  user_total: number;
}

export interface DashboardHourlyTrend {
  hour: string;
  login_count: number;
  operation_count: number;
}

export interface DashboardMonthlyVisit {
  count: number;
  month: string;
}

export interface DashboardNamedValue {
  name: string;
  value: number;
}

export interface DashboardRadarSeries {
  name: string;
  values: number[];
}

export interface DashboardAnalytics {
  device_radar: DashboardRadarSeries[];
  hourly_trends: DashboardHourlyTrend[];
  login_sources: DashboardNamedValue[];
  module_distribution: DashboardNamedValue[];
  monthly_visits: DashboardMonthlyVisit[];
  overview: DashboardOverview;
}

export interface DashboardSummary {
  apiHealthy: boolean;
  currentUserEmail: string;
  currentUserName: string;
  isSuperuser: boolean;
  userTotal: null | number;
}

export function getDashboardAnalyticsApi() {
  return requestClient.get<DashboardAnalytics>('/dashboard/analytics');
}

export function getHealthCheckApi() {
  return requestClient.get<boolean>('/utils/health-check');
}

export async function getDashboardSummaryApi(): Promise<DashboardSummary> {
  const [apiHealthy, currentUser] = await Promise.all([
    getHealthCheckApi(),
    getCurrentUserApi(),
  ]);

  const userTotal = currentUser.is_superuser
    ? (await listUsersApi({ page: 1, page_size: 1 })).total
    : null;

  return {
    apiHealthy,
    currentUserEmail: currentUser.email,
    currentUserName: currentUser.full_name || currentUser.email,
    isSuperuser: !!currentUser.is_superuser,
    userTotal,
  };
}
