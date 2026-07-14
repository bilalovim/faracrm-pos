import vkIconUrl from '../assets/vk.svg';

/**
 * Иконка мессенджера ВКонтакте.
 *
 * SVG-логотип отдаётся как URL (проект резолвит *.svg в строку), поэтому
 * рендерим через <img>. Принимает `size`, чтобы совпадать с интерфейсом
 * tabler-иконок и использоваться в темах/переключателях коннекторов.
 */
export function VkIcon({ size = 16 }: { size?: number }) {
  return (
    <img
      src={vkIconUrl}
      width={size}
      height={size}
      alt="VK"
      draggable={false}
      style={{ display: 'block' }}
    />
  );
}

export default VkIcon;
