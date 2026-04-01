"""
浏览器安装检查模块

用于检查 Playwright 浏览器是否已安装，若未安装则自动安装。
支持打包成 exe 后独立运行。
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger('actuator.browser')


def get_exe_dir() -> Path:
    """获取 exe 所在目录或脚本所在目录"""
    if getattr(sys, 'frozen', False):
        # 打包后的 exe
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path(__file__).parent


def get_browser_path() -> Path:
    """获取浏览器存储路径（相对于 exe 目录）"""
    return get_exe_dir() / "browsers"


def setup_playwright_env() -> None:
    """设置 Playwright 环境变量，使其使用相对路径存储浏览器"""
    browser_path = get_browser_path()
    # 设置 Playwright 浏览器存储路径
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browser_path)
    logger.info(f"Playwright 浏览器路径: {browser_path}")


def is_browser_installed(browser_type: str = 'chromium') -> bool:
    """检查浏览器是否已安装"""
    browser_path = get_browser_path()
    if not browser_path.exists():
        return False
    
    # 检查是否有浏览器目录
    browser_dirs = list(browser_path.glob(f'{browser_type}-*'))
    return len(browser_dirs) > 0


def install_browser(browser_type: str = 'chromium') -> bool:
    """安装 Playwright 浏览器"""
    browser_path = get_browser_path()
    browser_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"正在安装 {browser_type} 浏览器...")
    logger.info(f"安装路径: {browser_path}")
    logger.info("首次安装可能需要几分钟，请耐心等待...")
    
    try:
        # 设置环境变量
        env = os.environ.copy()
        env['PLAYWRIGHT_BROWSERS_PATH'] = str(browser_path)
        
        # 使用 playwright install 命令
        if getattr(sys, 'frozen', False):
            # 打包环境：使用内置的 playwright driver
            import playwright._impl._driver as driver
            driver_executable = driver.compute_driver_executable()
            # driver_executable 是一个元组: (node.exe, cli.js)
            if isinstance(driver_executable, tuple):
                cmd = list(driver_executable) + ['install', browser_type]
            else:
                cmd = [str(driver_executable), 'install', browser_type]
        else:
            # 开发环境
            cmd = [sys.executable, '-m', 'playwright', 'install', browser_type]
        
        logger.info(f"执行命令: {' '.join(str(c) for c in cmd)}")
        
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )
        
        if result.returncode == 0:
            logger.info(f"{browser_type} 浏览器安装成功!")
            return True
        else:
            logger.error(f"浏览器安装失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("浏览器安装超时")
        return False
    except Exception as e:
        logger.error(f"浏览器安装异常: {e}")
        return False


def ensure_browser(browser_type: str = 'chromium') -> bool:
    """确保浏览器已安装，未安装则自动安装"""
    setup_playwright_env()
    
    if is_browser_installed(browser_type):
        logger.info(f"{browser_type} 浏览器已安装")
        return True
    
    logger.info(f"未检测到 {browser_type} 浏览器，开始安装...")
    return install_browser(browser_type)


if __name__ == '__main__':
    # 测试
    logging.basicConfig(level=logging.INFO)
    ensure_browser('chromium')
