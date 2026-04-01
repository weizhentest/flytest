import { ref } from 'vue';

/**
 * 全局 LLM 配置刷新事件管理
 * 用于在配置更新时通知其他组件重新加载配置
 */

// 全局刷新触发器 - 使用时间戳确保每次都是新值
const llmConfigRefreshTrigger = ref<number>(0);

export function useLlmConfigRefresh() {
  /**
   * 触发 LLM 配置刷新
   * 在修改配置后调用此方法,通知所有监听组件
   */
  const triggerLlmConfigRefresh = () => {
    llmConfigRefreshTrigger.value = Date.now();
  };

  /**
   * 获取刷新触发器
   * 组件可以 watch 这个值来响应配置变化
   */
  const getRefreshTrigger = () => llmConfigRefreshTrigger;

  return {
    triggerLlmConfigRefresh,
    getRefreshTrigger
  };
}
