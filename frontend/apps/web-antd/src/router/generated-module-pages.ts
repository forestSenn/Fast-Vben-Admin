import type { ComponentRecordType } from '@vben/types';

export const modulePageMap: ComponentRecordType = {
  ...import.meta.glob('../modules/items/views/**/*.vue'),
};
