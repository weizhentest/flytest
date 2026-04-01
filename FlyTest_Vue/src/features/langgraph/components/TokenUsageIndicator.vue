<template>
  <div class="token-indicator" :class="statusClass">
    <svg viewBox="0 0 36 36" class="circular-chart">
      <!-- 背景圆环 -->
      <path
        class="circle-bg"
        d="M18 2.0845
          a 15.9155 15.9155 0 0 1 0 31.831
          a 15.9155 15.9155 0 0 1 0 -31.831"
      />
      <!-- 进度圆环 -->
      <path
        class="circle-progress"
        :stroke-dasharray="`${percentage}, 100`"
        d="M18 2.0845
          a 15.9155 15.9155 0 0 1 0 31.831
          a 15.9155 15.9155 0 0 1 0 -31.831"
      />
    </svg>
    <!-- 中心百分比文字 -->
    <span class="percentage-text">{{ displayPercentage }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  currentTokens: number;
  maxTokens: number;
}

const props = withDefaults(defineProps<Props>(), {
  currentTokens: 0,
  maxTokens: 128000
});

const percentage = computed(() => {
  if (props.maxTokens <= 0) return 0;
  const pct = (props.currentTokens / props.maxTokens) * 100;
  return Math.min(pct, 100);
});

const displayPercentage = computed(() => {
  const pct = percentage.value;
  // 小于1%时显示一位小数，否则显示整数
  if (pct < 1 && pct > 0) {
    return `${pct.toFixed(1)}%`;
  }
  return `${Math.round(pct)}%`;
});

const statusClass = computed(() => {
  if (percentage.value >= 80) return 'status-critical';
  if (percentage.value >= 50) return 'status-warning';
  return 'status-safe';
});
</script>

<style scoped>
.token-indicator {
  position: relative;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.2s;
}

.token-indicator:hover {
  transform: scale(1.1);
}

.circular-chart {
  width: 100%;
  height: 100%;
}

.circle-bg {
  fill: none;
  stroke: #e5e6eb;
  stroke-width: 3;
}

.circle-progress {
  fill: none;
  stroke-width: 3;
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease;
}

/* 安全状态 - 绿色 */
.status-safe .circle-progress {
  stroke: #00b42a;
}

/* 警告状态 - 黄色 */
.status-warning .circle-progress {
  stroke: #ff7d00;
}

/* 危险状态 - 红色 */
.status-critical .circle-progress {
  stroke: #f53f3f;
}

.percentage-text {
  position: absolute;
  font-size: 9px;
  font-weight: 600;
  color: var(--color-text-2);
}

.status-safe .percentage-text {
  color: #00b42a;
}

.status-warning .percentage-text {
  color: #ff7d00;
}

.status-critical .percentage-text {
  color: #f53f3f;
}
</style>
