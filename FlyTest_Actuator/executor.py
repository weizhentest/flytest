"""
UI自动化执行器 - Python Playwright执行引擎
使用Python原生Playwright库执行测试，无需Node.js依赖
"""

import asyncio
import logging
import time
import traceback
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright, expect

from models import StepResultModel, CaseResultModel

logger = logging.getLogger('actuator')


@dataclass
class StepConfig:
    """步骤配置"""
    step_id: int
    operation_type: str      # click, fill, goto, wait, assert等
    locator_type: str        # xpath, css, id等
    locator_value: str
    input_value: str = ''
    description: str = ''
    wait_time: float = 0
    
    # 步骤详情(公共步骤)
    details: list['StepConfig'] = field(default_factory=list)


@dataclass 
class PageStepConfig:
    """页面步骤配置"""
    page_step_id: int
    page_url: str
    page_name: str
    steps: list[StepConfig] = field(default_factory=list)


@dataclass
class TestCaseConfig:
    """测试用例配置"""
    case_id: int
    case_name: str
    page_steps: list[PageStepConfig] = field(default_factory=list)
    env_config: Optional[dict] = None


class PlaywrightExecutor:
    """Python原生Playwright执行器"""
    
    def __init__(
        self, 
        browser_type: str = 'chromium',
        headless: bool = False,
        persistent: bool = True,
        user_data_dir: str = './data/browser',
        launch_timeout: int = 30000,
        action_timeout: int = 30000,
        screenshot_dir: str = './data/screenshots',
        trace_enabled: bool = False,
        trace_dir: str = './data/traces',
        trace_screenshots: bool = True,
        trace_snapshots: bool = True,
        trace_sources: bool = False,
    ):
        self.browser_type = browser_type
        self.headless = headless
        self.persistent = persistent
        self.user_data_dir = user_data_dir
        self.launch_timeout = launch_timeout
        self.action_timeout = action_timeout
        self.screenshot_dir = screenshot_dir
        
        # Trace 配置
        self.trace_enabled = trace_enabled
        self.trace_dir = trace_dir
        self.trace_screenshots = trace_screenshots
        self.trace_snapshots = trace_snapshots
        self.trace_sources = trace_sources
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._stop_requested = False
        self._current_trace_path: Optional[str] = None
        
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.screenshot_dir).mkdir(parents=True, exist_ok=True)
        if self.trace_enabled:
            Path(self.trace_dir).mkdir(parents=True, exist_ok=True)
    
    async def init_browser(self) -> None:
        """初始化浏览器"""
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        
        browser_launcher = getattr(self._playwright, self.browser_type)
        
        if self.persistent:
            self._context = await browser_launcher.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                timeout=self.launch_timeout,
            )
            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()
        else:
            self._browser = await browser_launcher.launch(
                headless=self.headless,
                timeout=self.launch_timeout,
            )
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
        
        self._page.set_default_timeout(self.action_timeout)
        logger.info(f"浏览器已初始化: {self.browser_type}, headless={self.headless}")
    
    async def close(self) -> None:
        """关闭浏览器"""
        if self._context:
            await self._context.close()
            self._context = None
            self._page = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("浏览器已关闭")
    
    @asynccontextmanager
    async def browser_session(self):
        """浏览器会话上下文管理器"""
        await self.init_browser()
        try:
            yield self._page
        finally:
            await self.close()
    
    @asynccontextmanager
    async def browser_session_with_trace(self, trace_name: str = 'trace'):
        """带 Trace 的浏览器会话上下文管理器
        
        Args:
            trace_name: trace 文件名前缀（不含扩展名）
            
        Yields:
            Page: 页面对象
            
        Returns:
            trace 文件路径（通过 self._current_trace_path 获取）
        """
        await self.init_browser()
        self._current_trace_path = None
        
        try:
            # 启动 Trace
            if self.trace_enabled and self._context:
                await self._context.tracing.start(
                    screenshots=self.trace_screenshots,
                    snapshots=self.trace_snapshots,
                    sources=self.trace_sources,
                )
                logger.debug(f"Trace 已启动: screenshots={self.trace_screenshots}, snapshots={self.trace_snapshots}")
            
            yield self._page
            
        finally:
            # 停止 Trace 并保存
            if self.trace_enabled and self._context:
                try:
                    timestamp = int(time.time() * 1000)
                    trace_path = f"{self.trace_dir}/{trace_name}_{timestamp}.zip"
                    await self._context.tracing.stop(path=trace_path)
                    self._current_trace_path = trace_path
                    logger.info(f"Trace 已保存: {trace_path}")
                except Exception as e:
                    logger.error(f"保存 Trace 失败: {e}")
            
            await self.close()
    
    def get_current_trace_path(self) -> Optional[str]:
        """获取当前执行的 trace 文件路径"""
        return self._current_trace_path

    def stop(self):
        """请求停止执行"""
        self._stop_requested = True
    
    def _get_locator(self, page: Page, locator_type: str, locator_value: str):
        """根据定位类型获取元素定位器"""
        locator_map = {
            'xpath': lambda: page.locator(f"xpath={locator_value}"),
            'css': lambda: page.locator(locator_value),
            'id': lambda: page.locator(f"#{locator_value}"),
            'name': lambda: page.locator(f"[name='{locator_value}']"),
            'text': lambda: page.get_by_text(locator_value),
            'role': lambda: page.get_by_role(locator_value),
            'placeholder': lambda: page.get_by_placeholder(locator_value),
            'label': lambda: page.get_by_label(locator_value),
            'testid': lambda: page.get_by_test_id(locator_value),
        }
        return locator_map.get(locator_type, lambda: page.locator(locator_value))()
    
    async def _execute_step(self, page: Page, step: StepConfig) -> tuple[bool, str, str | None]:
        """执行单个步骤
        
        Returns:
            tuple: (成功与否, 消息, 截图路径(可选))
        """
        operation = step.operation_type.lower()
        screenshot_path: str | None = None
        
        # 等待时间（仅当用户明确设置 > 0 时才等待，用于特殊场景）
        # 注意：Playwright 自带 Auto-waiting，一般不需要手动等待
        if step.wait_time > 0:
            logger.debug(f"步骤 {step.step_id}: 强制等待 {step.wait_time}s（建议设为0让Playwright自动等待）")
            await page.wait_for_timeout(int(step.wait_time * 1000))
        
        # 记录开始时间
        op_start = time.time()
        
        # screenshot 操作特殊处理，保存路径
        if operation == 'screenshot':
            screenshot_path = step.input_value or f"{self.screenshot_dir}/step_{step.step_id}.png"
            await page.screenshot(path=screenshot_path)
            logger.debug(f"步骤 {step.step_id}: screenshot 耗时 {time.time() - op_start:.2f}s")
            return True, f"页面操作 {operation} 执行成功", screenshot_path
        
        # 页面操作（不需要定位器）
        def _parse_wait_timeout(value: str) -> int:
            """解析等待时间（毫秒）"""
            if not value:
                return 1000  # 默认 1 秒
            try:
                return int(float(value))
            except ValueError:
                return 1000

        page_operations = {
            'goto': lambda: page.goto(step.input_value),
            'reload': lambda: page.reload(),
            'go_back': lambda: page.go_back(),
            'go_forward': lambda: page.go_forward(),
            'wait': lambda: page.wait_for_timeout(_parse_wait_timeout(step.input_value)),
            'wait_load': lambda: page.wait_for_load_state("load"),
            'wait_network': lambda: page.wait_for_load_state("networkidle"),
        }
        
        if operation in page_operations:
            await page_operations[operation]()
            logger.debug(f"步骤 {step.step_id}: {operation} 耗时 {time.time() - op_start:.2f}s")
            return True, f"页面操作 {operation} 执行成功", None
        
        # 元素操作（需要定位器）- 先验证定位器是否有效
        if not step.locator_value or not step.locator_value.strip():
            return False, f"元素定位器为空，请在元素管理中配置定位表达式（步骤: {step.description or step.step_id}）", None
        
        locator_start = time.time()
        locator = self._get_locator(page, step.locator_type, step.locator_value)
        
        # 先等待元素可见（更短的超时时间加快检测）
        try:
            await locator.wait_for(state="visible", timeout=5000)
        except Exception:
            # 5秒内没有可见，继续尝试操作（可能是 hidden 元素）
            pass
        
        locator_time = time.time() - locator_start
        logger.debug(f"步骤 {step.step_id}: 定位元素 [{step.locator_type}={step.locator_value}] 耗时 {locator_time:.2f}s")
        
        element_operations = {
            'click': lambda: locator.click(),
            'dblclick': lambda: locator.dblclick(),
            'fill': lambda: locator.fill(step.input_value),
            'type': lambda: locator.type(step.input_value),
            'clear': lambda: locator.fill(""),
            'check': lambda: locator.check(),
            'uncheck': lambda: locator.uncheck(),
            'select': lambda: locator.select_option(step.input_value),
            'hover': lambda: locator.hover(),
            'focus': lambda: locator.focus(),
            'press': lambda: locator.press(step.input_value),
            'upload': lambda: locator.set_input_files(step.input_value),
        }
        
        if operation in element_operations:
            action_start = time.time()
            await element_operations[operation]()
            action_time = time.time() - action_start
            logger.debug(f"步骤 {step.step_id}: {operation} 操作耗时 {action_time:.2f}s (总计 {time.time() - op_start:.2f}s)")
            return True, f"元素操作 {operation} 执行成功", None
        
        # 断言操作
        if operation.startswith('assert_'):
            assert_type = operation.replace('assert_', '')
            assert_operations = {
                'visible': lambda: expect(locator).to_be_visible(),
                'hidden': lambda: expect(locator).to_be_hidden(),
                'enabled': lambda: expect(locator).to_be_enabled(),
                'disabled': lambda: expect(locator).to_be_disabled(),
                'checked': lambda: expect(locator).to_be_checked(),
                'text': lambda: expect(locator).to_have_text(step.input_value),
                'value': lambda: expect(locator).to_have_value(step.input_value),
                'contain_text': lambda: expect(locator).to_contain_text(step.input_value),
                'url': lambda: expect(page).to_have_url(step.input_value),
                'title': lambda: expect(page).to_have_title(step.input_value),
            }
            if assert_type in assert_operations:
                await assert_operations[assert_type]()
                logger.debug(f"步骤 {step.step_id}: assert_{assert_type} 耗时 {time.time() - op_start:.2f}s")
                return True, f"断言 {assert_type} 通过", None
        
        return False, f"未知操作类型: {operation}", None
    
    async def execute_step(self, step: StepConfig, page_url: str = '') -> StepResultModel:
        """执行单个步骤（独立浏览器会话）"""
        start_time = time.time()
        
        try:
            async with self.browser_session() as page:
                if page_url:
                    await page.goto(page_url)
                
                success, message, step_screenshot = await self._execute_step(page, step)
                duration = time.time() - start_time
                
                return StepResultModel(
                    step_id=step.step_id,
                    status='success' if success else 'failed',
                    message=message,
                    description=step.description or step.operation_type,
                    duration=duration,
                    element_found=success,
                    screenshot=step_screenshot
                )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"步骤执行失败: {e}\n{traceback.format_exc()}")
            return StepResultModel(
                step_id=step.step_id,
                status='failed',
                message=str(e),
                description=step.description or step.operation_type,
                duration=duration,
                element_found=False
            )
    
    async def execute_test_case(self, config: TestCaseConfig) -> CaseResultModel:
        """执行测试用例（支持 Trace 记录）"""
        start_time = time.time()
        step_results = []
        passed_steps = 0
        failed_steps = 0
        total_steps = sum(len(ps.steps) for ps in config.page_steps)
        
        self._stop_requested = False
        trace_name = f"case_{config.case_id}"
        
        try:
            # 使用带 trace 的浏览器会话
            async with self.browser_session_with_trace(trace_name) as page:
                logger.info(f"开始执行用例: {config.case_name}")

                # 浏览器启动后，立即导航到环境配置的 base_url
                base_url = ''
                if config.env_config:
                    base_url = config.env_config.get('base_url', '') or ''
                if base_url:
                    logger.info(f"导航到环境 base_url: {base_url}")
                    await page.goto(base_url, wait_until="networkidle")

                for page_step in config.page_steps:
                    if self._stop_requested:
                        raise Exception("用例被手动停止")

                    logger.info(f"执行页面步骤: {page_step.page_name}")

                    # 检测页面跳转：仅当下一个页面 URL 与当前不同时才等待
                    if page_step.page_url:
                        current_url = page.url
                        expected_url = page_step.page_url.rstrip('/')
                        
                        # 只有当期望的 URL 与当前 URL 不同时，才等待跳转
                        if expected_url not in current_url:
                            try:
                                # 短暂等待，检测是否有 URL 变化
                                await page.wait_for_url(
                                    lambda url: url != current_url,
                                    timeout=2000
                                )
                                logger.debug(f"检测到页面跳转: {current_url} -> {page.url}")
                            except Exception:
                                # 没有页面跳转是正常情况
                                pass
                    
                    # 执行页面内的步骤
                    for step in page_step.steps:
                        if self._stop_requested:
                            raise Exception("用例被手动停止")
                        
                        step_start = time.time()
                        try:
                            success, message, step_screenshot = await self._execute_step(page, step)
                            step_duration = time.time() - step_start

                            step_result = StepResultModel(
                                step_id=step.step_id,
                                status='success' if success else 'failed',
                                message=message,
                                description=step.description or step.operation_type,
                                duration=step_duration,
                                element_found=success,
                                screenshot=step_screenshot  # 保存截图操作的路径
                            )

                            if success:
                                passed_steps += 1
                                logger.debug(f"  ✅ {step.description or step.operation_type}")
                            else:
                                failed_steps += 1
                                logger.warning(f"  ❌ {step.description or step.operation_type}: {message}")
                                # 失败时额外截图
                                if not step_screenshot:
                                    screenshot_path = f"{self.screenshot_dir}/fail_{config.case_id}_{step.step_id}.png"
                                    await page.screenshot(path=screenshot_path)
                                    step_result.screenshot = screenshot_path

                        except Exception as step_error:
                            step_duration = time.time() - step_start
                            failed_steps += 1
                            error_msg = str(step_error)
                            logger.error(f"  ❌ {step.description or step.operation_type}: {error_msg}")

                            # 失败时截图
                            try:
                                screenshot_path = f"{self.screenshot_dir}/error_{config.case_id}_{step.step_id}.png"
                                await page.screenshot(path=screenshot_path)
                            except:
                                screenshot_path = None

                            step_result = StepResultModel(
                                step_id=step.step_id,
                                status='failed',
                                message=error_msg,
                                description=step.description or step.operation_type,
                                duration=step_duration,
                                element_found=False,
                                screenshot=screenshot_path
                            )
                        
                        step_results.append(step_result)

                    # 页面步骤执行完毕后，等待页面稳定（处理可能的页面跳转）
                    try:
                        await page.wait_for_load_state("load", timeout=10000)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        logger.debug(f"页面步骤 {page_step.page_name} 执行后等待页面稳定超时，继续执行")

                duration = time.time() - start_time
                status = 'success' if failed_steps == 0 else 'failed'
                message = f"用例执行{'成功' if status == 'success' else '失败'}: 通过 {passed_steps}/{total_steps}"
                logger.info(f"✅ {message}" if status == 'success' else f"❌ {message}")
                
                # 获取 trace 文件路径（会在 browser_session_with_trace 结束时设置）
                trace_path = None
            
            # 会话结束后获取 trace 路径
            trace_path = self.get_current_trace_path()
            if trace_path:
                logger.info(f"用例执行 Trace 已记录: {trace_path}")
            
            return CaseResultModel(
                case_id=config.case_id,
                status=status,
                message=message,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps,
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"用例执行异常: {error_msg}\n{traceback.format_exc()}")
            
            # 尝试获取 trace 路径（可能已保存）
            trace_path = self.get_current_trace_path()
            
            return CaseResultModel(
                case_id=config.case_id,
                status='failed',
                message=error_msg,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps + (total_steps - passed_steps - failed_steps),
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )

    async def execute_page_step(self, config: PageStepConfig) -> list[StepResultModel]:
        """执行单个页面步骤（包含多个操作）- 使用同一个浏览器会话"""
        step_results = []
        
        try:
            async with self.browser_session() as page:
                logger.info(f"开始执行页面步骤: {config.page_name}")
                
                # 导航到页面
                if config.page_url:
                    nav_start = time.time()
                    await page.goto(config.page_url)
                    await page.wait_for_load_state("domcontentloaded")
                    logger.debug(f"页面导航 {config.page_name} 耗时 {time.time() - nav_start:.2f}s")
                
                # 执行页面内的所有步骤
                for step in config.steps:
                    step_start = time.time()
                    try:
                        success, message, step_screenshot = await self._execute_step(page, step)
                        step_duration = time.time() - step_start

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='success' if success else 'failed',
                            message=message,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=success,
                            screenshot=step_screenshot
                        )
                        step_results.append(step_result)

                        if success:
                            logger.debug(f"  ✅ {step.description or step.operation_type}")
                        else:
                            logger.warning(f"  ❌ {step.description or step.operation_type}: {message}")
                            # 失败时额外截图
                            if not step_screenshot:
                                screenshot_path = f"{self.screenshot_dir}/fail_ps_{config.page_step_id}_{step.step_id}.png"
                                await page.screenshot(path=screenshot_path)
                                step_result.screenshot = screenshot_path
                            break  # 步骤失败时停止执行后续步骤

                    except Exception as step_error:
                        step_duration = time.time() - step_start
                        error_msg = str(step_error)
                        logger.error(f"  ❌ {step.description or step.operation_type}: {error_msg}")

                        # 失败时截图
                        try:
                            screenshot_path = f"{self.screenshot_dir}/error_ps_{config.page_step_id}_{step.step_id}.png"
                            await page.screenshot(path=screenshot_path)
                        except:
                            screenshot_path = None

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='failed',
                            message=error_msg,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=False,
                            screenshot=screenshot_path
                        )
                        step_results.append(step_result)
                        break  # 步骤失败时停止执行后续步骤
                        
        except Exception as e:
            logger.error(f"页面步骤执行异常: {e}\n{traceback.format_exc()}")
            # 如果连浏览器都打不开，返回一个失败结果
            if not step_results:
                step_results.append(StepResultModel(
                    step_id=0,
                    status='failed',
                    message=str(e),
                    duration=0,
                    element_found=False
                ))

        return step_results

    async def _execute_case_on_context(
        self,
        context: BrowserContext,
        config: TestCaseConfig,
        trace_enabled: bool = False
    ) -> CaseResultModel:
        """在独立上下文中执行用例（用于并发执行）"""
        start_time = time.time()
        step_results = []
        passed_steps = 0
        failed_steps = 0
        total_steps = sum(len(ps.steps) for ps in config.page_steps)
        trace_path = None

        try:
            # 启动 Trace
            if trace_enabled:
                await context.tracing.start(
                    screenshots=self.trace_screenshots,
                    snapshots=self.trace_snapshots,
                    sources=self.trace_sources,
                )

            page = await context.new_page()
            page.set_default_timeout(self.action_timeout)

            logger.info(f"[并发] 开始执行用例: {config.case_name}")

            # 浏览器启动后，立即导航到环境配置的 base_url
            base_url = ''
            if config.env_config:
                base_url = config.env_config.get('base_url', '') or ''
            if base_url:
                logger.info(f"[并发] 导航到环境 base_url: {base_url}")
                await page.goto(base_url, wait_until="networkidle")

            for page_step in config.page_steps:
                if self._stop_requested:
                    raise Exception("用例被手动停止")

                logger.info(f"[并发] 执行页面步骤: {page_step.page_name}")

                # 检测页面跳转：仅当下一个页面 URL 与当前不同时才等待
                if page_step.page_url:
                    current_url = page.url
                    expected_url = page_step.page_url.rstrip('/')

                    # 只有当期望的 URL 与当前 URL 不同时，才等待跳转
                    if expected_url not in current_url:
                        try:
                            # 短暂等待，检测是否有 URL 变化
                            await page.wait_for_url(
                                lambda url: url != current_url,
                                timeout=2000
                            )
                            logger.debug(f"[并发] 检测到页面跳转: {current_url} -> {page.url}")
                        except Exception:
                            # 没有页面跳转是正常情况
                            pass

                # 执行页面内的步骤
                for step in page_step.steps:
                    if self._stop_requested:
                        raise Exception("用例被手动停止")

                    step_start = time.time()
                    try:
                        success, message, step_screenshot = await self._execute_step(page, step)
                        step_duration = time.time() - step_start

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='success' if success else 'failed',
                            message=message,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=success,
                            screenshot=step_screenshot
                        )

                        if success:
                            passed_steps += 1
                        else:
                            failed_steps += 1
                            if not step_screenshot:
                                screenshot_path = f"{self.screenshot_dir}/fail_{config.case_id}_{step.step_id}.png"
                                await page.screenshot(path=screenshot_path)
                                step_result.screenshot = screenshot_path

                    except Exception as step_error:
                        step_duration = time.time() - step_start
                        failed_steps += 1
                        error_msg = str(step_error)

                        try:
                            screenshot_path = f"{self.screenshot_dir}/error_{config.case_id}_{step.step_id}.png"
                            await page.screenshot(path=screenshot_path)
                        except:
                            screenshot_path = None

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='failed',
                            message=error_msg,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=False,
                            screenshot=screenshot_path
                        )

                    step_results.append(step_result)

                # 页面步骤执行完毕后，等待页面稳定（处理可能的页面跳转）
                try:
                    await page.wait_for_load_state("load", timeout=10000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    logger.debug(f"[并发] 页面步骤 {page_step.page_name} 执行后等待页面稳定超时，继续执行")

            duration = time.time() - start_time
            status = 'success' if failed_steps == 0 else 'failed'
            message = f"用例执行{'成功' if status == 'success' else '失败'}: 通过 {passed_steps}/{total_steps}"

            # 保存 Trace
            if trace_enabled:
                trace_path = f"{self.trace_dir}/case_{config.case_id}_{int(time.time())}.zip"
                await context.tracing.stop(path=trace_path)

            await page.close()

            logger.info(f"[并发] {'✅' if status == 'success' else '❌'} {message}")

            return CaseResultModel(
                case_id=config.case_id,
                status=status,
                message=message,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps,
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"[并发] 用例执行异常: {error_msg}")

            # 尝试保存 Trace
            if trace_enabled:
                try:
                    trace_path = f"{self.trace_dir}/case_{config.case_id}_{int(time.time())}.zip"
                    await context.tracing.stop(path=trace_path)
                except:
                    pass

            return CaseResultModel(
                case_id=config.case_id,
                status='failed',
                message=error_msg,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps + (total_steps - passed_steps - failed_steps),
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )

    async def execute_batch_concurrent(
        self,
        configs: list[TestCaseConfig],
        max_concurrent: int = 3,
        on_result = None
    ) -> list[CaseResultModel]:
        """并发执行多个用例

        Args:
            configs: 用例配置列表
            max_concurrent: 最大并发数
            on_result: 单个用例完成时的回调函数 (可选)

        Returns:
            用例执行结果列表
        """
        if not configs:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        # 确保浏览器已初始化（非持久化模式）
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        browser_launcher = getattr(self._playwright, self.browser_type)
        browser = await browser_launcher.launch(
            headless=self.headless,
            timeout=self.launch_timeout,
        )

        logger.info(f"[并发执行] 开始执行 {len(configs)} 个用例, 最大并发数: {max_concurrent}")

        async def run_with_limit(config: TestCaseConfig):
            async with semaphore:
                # 每个用例独立的浏览器上下文
                context = await browser.new_context()
                try:
                    result = await self._execute_case_on_context(
                        context,
                        config,
                        trace_enabled=self.trace_enabled
                    )
                    if on_result:
                        await on_result(result)
                    return result
                finally:
                    await context.close()

        try:
            # 并发执行所有用例
            results = await asyncio.gather(
                *[run_with_limit(c) for c in configs],
                return_exceptions=True
            )

            # 处理异常结果
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    final_results.append(CaseResultModel(
                        case_id=configs[i].case_id,
                        status='failed',
                        message=str(result),
                        total_steps=0,
                        passed_steps=0,
                        failed_steps=0,
                        duration=0,
                        steps=[]
                    ))
                else:
                    final_results.append(result)

            logger.info(f"[并发执行] 完成, 成功: {sum(1 for r in final_results if r.status == 'success')}/{len(final_results)}")
            return final_results

        finally:
            await browser.close()
