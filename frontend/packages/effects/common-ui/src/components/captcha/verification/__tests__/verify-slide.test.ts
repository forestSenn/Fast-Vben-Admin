import { flushPromises, mount } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import VerifySlide from '../verify-slide.vue';

describe('verify-slide', () => {
  it('moves the handle with the puzzle piece and progress bar', async () => {
    const wrapper = mount(VerifySlide, {
      props: {
        getCaptchaApi: vi.fn().mockResolvedValue({
          repCode: '0000',
          repData: {
            imageHeight: 200,
            imageWidth: 400,
            jigsawImageBase64: '',
            originalImageBase64: '',
            pieceY: 72,
            secretKey: '0123456789abcdef',
            token: 'test-token',
          },
        }),
      },
    });
    await flushPromises();

    const bar = wrapper.get('.verify-bar-area').element as HTMLElement;
    vi.spyOn(bar, 'getBoundingClientRect').mockReturnValue({
      bottom: 42,
      height: 42,
      left: 0,
      right: 400,
      top: 0,
      width: 400,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    const handle = wrapper.get('.verify-move-block');
    Object.defineProperty(handle.element, 'setPointerCapture', {
      value: vi.fn(),
    });

    await handle.trigger('pointerdown', { clientX: 22, pointerId: 1 });
    window.dispatchEvent(
      new PointerEvent('pointermove', { clientX: 142, pointerId: 1 }),
    );
    await wrapper.vm.$nextTick();

    expect(handle.attributes('style')).toContain('left: 120px');
    expect(wrapper.get('.verify-piece').attributes('style')).toContain(
      'left: 120px',
    );
    expect(wrapper.get('.verify-left-bar').attributes('style')).toContain(
      'width: 164px',
    );

    wrapper.unmount();
  });
});
