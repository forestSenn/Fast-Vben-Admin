<script setup lang="ts">
import type { VerificationProps } from './typing';

import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { aesEncrypt } from './utils/ase';

const props = withDefaults(defineProps<VerificationProps>(), {
  barSize: () => ({ height: '42px', width: '400px' }),
  captchaType: 'blockPuzzle',
  explain: '',
  imgSize: () => ({ height: '200px', width: '400px' }),
});

const emit = defineEmits<{
  onError: [unknown];
  onReady: [unknown];
  onSuccess: [data: { captchaVerification: string }];
}>();

const imageWidth = ref(400);
const imageHeight = ref(200);
const pieceY = ref(72);
const backImgBase = ref('');
const blockImgBase = ref('');
const backToken = ref('');
const secretKey = ref('');
const moveBlockLeft = ref(0);
const leftBarWidth = ref(0);
const text = ref('');
const tipWords = ref('');
const passFlag = ref(false);
const isMoving = ref(false);
const startLeft = ref(0);
const startMoveTime = ref(0);
const barElement = ref<HTMLElement>();

const pieceStyle = computed(() => ({
  left: `${moveBlockLeft.value}px`,
  top: `${(pieceY.value / imageHeight.value) * 100}%`,
}));

const barStyle = computed(() => ({ width: `${leftBarWidth.value}px` }));
const moveBlockStyle = computed(() => ({ left: `${moveBlockLeft.value}px` }));

function onPointerDown(event: PointerEvent) {
  if (passFlag.value || !barElement.value) return;
  const rect = barElement.value.getBoundingClientRect();
  startLeft.value = event.clientX - rect.left - moveBlockLeft.value;
  startMoveTime.value = Date.now();
  isMoving.value = true;
  text.value = '';
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function onPointerMove(event: PointerEvent) {
  if (!isMoving.value || !barElement.value) return;
  const rect = barElement.value.getBoundingClientRect();
  const max = rect.width - 44;
  const next = Math.max(0, Math.min(max, event.clientX - rect.left - startLeft.value));
  moveBlockLeft.value = next;
  leftBarWidth.value = next + 44;
}

async function onPointerUp() {
  if (!isMoving.value) return;
  isMoving.value = false;
  const renderedWidth = barElement.value?.getBoundingClientRect().width || imageWidth.value;
  const scaledX = (moveBlockLeft.value * 310) / renderedWidth;
  const point = JSON.stringify({ x: scaledX, y: 5 });
  try {
  const response = await props.checkCaptchaApi?.({
      captchaType: props.captchaType,
      pointJson: aesEncrypt(point, secretKey.value),
      token: backToken.value,
    });
    const result = response?.data ?? response;
    if (result?.repCode !== '0000') {
      throw new Error(result?.repMsg || '验证失败');
    }
    passFlag.value = true;
    tipWords.value = `${((Date.now() - startMoveTime.value) / 1000).toFixed(2)}s 验证通过`;
    text.value = '验证通过';
    emit('onSuccess', {
      captchaVerification: aesEncrypt(
        `${backToken.value}---${point}`,
        secretKey.value,
      ),
    });
  } catch (error) {
    passFlag.value = false;
    tipWords.value = error instanceof Error ? error.message : '验证失败';
    emit('onError', error);
    window.setTimeout(() => refresh(), 700);
  }
}

async function refresh() {
  passFlag.value = false;
  moveBlockLeft.value = 0;
  leftBarWidth.value = 0;
  tipWords.value = '';
  text.value = props.explain || '请按住滑块拖动';
  const response = await props.getCaptchaApi?.({ captchaType: props.captchaType });
  const result = response?.data ?? response;
  if (result?.repCode !== '0000' || !result.repData) {
    throw new Error(result?.repMsg || '验证码加载失败');
  }
  const data = result.repData;
  imageWidth.value = Number(data.imageWidth || 400);
  imageHeight.value = Number(data.imageHeight || 200);
  pieceY.value = Number(data.pieceY || 72);
  backToken.value = String(data.token);
  secretKey.value = String(data.secretKey);
  backImgBase.value = `data:image/png;base64,${data.originalImageBase64}`;
  blockImgBase.value = `data:image/png;base64,${data.jigsawImageBase64}`;
  emit('onReady', result);
}

onMounted(() => {
  void refresh();
  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
});

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove);
  window.removeEventListener('pointerup', onPointerUp);
});

defineExpose({ refresh });
</script>

<template>
  <div>
    <div class="verify-img-panel" :style="{ aspectRatio: `${imageWidth} / ${imageHeight}` }">
      <img class="verify-background" :src="backImgBase" alt="滑动验证码背景" />
      <img v-if="blockImgBase" class="verify-piece" :style="pieceStyle" :src="blockImgBase" alt="" />
      <div v-if="tipWords" class="verify-tips" :class="{ success: passFlag }">{{ tipWords }}</div>
    </div>
    <div ref="barElement" class="verify-bar-area">
      <div class="verify-left-bar" :style="barStyle"></div>
      <span class="verify-msg">{{ text }}</span>
      <div
        class="verify-move-block"
        :style="moveBlockStyle"
        @pointerdown="onPointerDown"
      >
        {{ passFlag ? '✓' : '➜' }}
      </div>
    </div>
  </div>
</template>
