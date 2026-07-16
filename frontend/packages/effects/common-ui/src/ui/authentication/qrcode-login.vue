<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';

import { $t } from '@vben/locales';

import { VbenButton } from '@vben-core/shadcn-ui';

import { useQRCode } from '@vueuse/integrations/useQRCode';

import Title from './auth-title.vue';

interface Props {
  /**
   * @zh_CN 是否处于加载处理状态
   */
  loading?: boolean;
  /**
   * @zh_CN 登录路径
   */
  loginPath?: string;
  /**
   * @zh_CN 标题
   */
  title?: string;
  /**
   * @zh_CN 描述
   */
  subTitle?: string;
  /**
   * @zh_CN 按钮文本
   */
  submitButtonText?: string;
  /**
   * @zh_CN 描述
   */
  description?: string;
  /**
   * @zh_CN 是否显示返回按钮
   */
  showBack?: boolean;
  /**
   * @zh_CN 二维码内容
   */
  qrCodeValue?: string;
  /**
   * @zh_CN 二维码是否已过期
   */
  expired?: boolean;
}

defineOptions({
  name: 'AuthenticationQrCodeLogin',
});

const emit = defineEmits<{ refresh: [] }>();

const props = withDefaults(defineProps<Props>(), {
  description: '',
  loading: false,
  showBack: true,
  loginPath: '/auth/login',
  submitButtonText: '',
  subTitle: '',
  title: '',
  qrCodeValue: 'https://vben.vvbin.cn',
  expired: false,
});

const router = useRouter();

const qrcode = useQRCode(computed(() => props.qrCodeValue), {
  errorCorrectionLevel: 'H',
  margin: 4,
});

function goToLogin() {
  router.push(props.loginPath);
}
</script>

<template>
  <div class="mx-auto w-full max-w-md">
    <Title>
      <slot name="title">
        {{ title || $t('authentication.welcomeBack') }} 📱
      </slot>
      <template #desc>
        <span class="text-muted-foreground">
          <slot name="subTitle">
            {{ subTitle || $t('authentication.qrcodeSubtitle') }}
          </slot>
        </span>
      </template>
    </Title>

    <div class="mt-6 flex-col-center">
      <div class="relative flex w-1/2 items-center justify-center">
        <img
          :class="{ 'opacity-20': expired || loading }"
          :src="qrcode"
          alt="qrcode"
          class="w-full"
        />
        <VbenButton
          v-if="expired"
          class="absolute"
          size="sm"
          @click="emit('refresh')"
        >
          重新获取
        </VbenButton>
      </div>
      <p class="mt-4 text-sm text-muted-foreground">
        <slot name="description">
          {{ description || $t('authentication.qrcodePrompt') }}
        </slot>
      </p>
    </div>

    <VbenButton
      v-if="showBack"
      class="mt-4 w-full"
      variant="outline"
      @click="goToLogin()"
    >
      {{ $t('common.back') }}
    </VbenButton>
  </div>
</template>
