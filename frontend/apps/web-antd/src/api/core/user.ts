import type { UserInfo } from '@vben/types';

import { getCurrentUserApi } from './auth';

/**
 * 获取用户信息
 */
export async function getUserInfoApi() {
  const user = await getCurrentUserApi();
  const role = user.is_superuser ? 'super' : 'user';

  return {
    avatar: '',
    desc: user.is_superuser ? 'Super administrator' : 'User',
    homePath: '/dashboard',
    realName: user.full_name || user.email,
    roles: [role],
    token: '',
    userId: user.id,
    username: user.email,
  } satisfies UserInfo;
}
