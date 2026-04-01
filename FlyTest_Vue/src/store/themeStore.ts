import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

type ThemeMode = 'default' | 'black';

const THEME_STORAGE_KEY = 'flytest-theme-mode';

const isBrowser = () => typeof window !== 'undefined' && typeof document !== 'undefined';

const getSavedTheme = (): ThemeMode => {
  if (!isBrowser()) {
    return 'default';
  }

  const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
  return savedTheme === 'black' ? 'black' : 'default';
};

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<ThemeMode>('default');
  const isBlack = computed(() => theme.value === 'black');

  const applyTheme = (nextTheme: ThemeMode) => {
    theme.value = nextTheme;

    if (!isBrowser()) {
      return;
    }

    if (nextTheme === 'black') {
      document.documentElement.dataset.theme = 'black';
    } else {
      delete document.documentElement.dataset.theme;
    }

    if (document.body) {
      if (nextTheme === 'black') {
        document.body.setAttribute('arco-theme', 'dark');
      } else {
        document.body.removeAttribute('arco-theme');
      }
    }

    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  };

  const initializeTheme = () => {
    applyTheme(getSavedTheme());
  };

  const toggleTheme = () => {
    applyTheme(isBlack.value ? 'default' : 'black');
  };

  return {
    theme,
    isBlack,
    initializeTheme,
    toggleTheme,
  };
});
