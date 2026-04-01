"""
GUI 登录窗口模块

提供 PySide6 图形界面登录功能，支持：
- 用户名/密码输入
- 服务器地址配置
- 登录验证
- 配置记忆
- 执行器设置（浏览器类型、无头模式等）
"""

import asyncio
import sys
from typing import Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import httpx
import tomli
import tomli_w
from pathlib import Path


class LoginWorker(QThread):
    """异步登录工作线程"""
    
    login_success = Signal(str, str)  # (access_token, refresh_token)
    login_failed = Signal(str)  # error_message
    
    def __init__(
        self,
        api_url: str,
        username: str,
        password: str,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.api_url = api_url.rstrip('/')
        self.username = username
        self.password = password
    
    def run(self):
        """执行登录验证"""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"{self.api_url}/api/token/",
                    json={"username": self.username, "password": self.password}
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    # 兼容不同的响应格式
                    if data.get('status') == 'success':
                        access = data['data']['access']
                        refresh = data['data'].get('refresh', '')
                    else:
                        access = data.get('access', '')
                        refresh = data.get('refresh', '')
                    
                    if access:
                        self.login_success.emit(access, refresh)
                    else:
                        self.login_failed.emit("登录响应格式错误")
                elif resp.status_code == 401:
                    self.login_failed.emit("用户名或密码错误")
                else:
                    self.login_failed.emit(f"服务器错误: {resp.status_code}")
                    
        except httpx.ConnectError:
            self.login_failed.emit("无法连接到服务器，请检查地址是否正确")
        except httpx.TimeoutException:
            self.login_failed.emit("连接超时，请检查网络")
        except Exception as e:
            self.login_failed.emit(f"登录失败: {str(e)}")


class LoginWindow(QDialog):
    """执行器登录窗口"""
    
    def __init__(self, config_path: str = "config.toml", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config_path = Path(config_path)
        self._config = self._load_config()
        
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._login_worker: Optional[LoginWorker] = None
        
        self._init_ui()
        self._load_saved_credentials()
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        if self.config_path.exists():
            with open(self.config_path, 'rb') as f:
                return tomli.load(f)
        return {}
    
    def _save_config(self):
        """保存配置文件"""
        with open(self.config_path, 'wb') as f:
            tomli_w.dump(self._config, f)
    
    def _init_ui(self):
        """初始化界面 - 左右分栏设计"""
        self.setWindowTitle("FlyTest 执行器登录")
        self.setFixedSize(920, 640)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("background-color: #f0f2f5;")
        
        # 设置窗口图标
        window_icon = self._get_window_icon()
        if window_icon:
            self.setWindowIcon(window_icon)

        # 主布局 - 水平分栏
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== 左侧品牌区域 ==========
        left_panel = QFrame()
        left_panel.setFixedWidth(400)
        left_panel.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1E88E5, stop:0.5 #1565C0, stop:1 #0D47A1);
                border-radius: 0;
            }
        """)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(40, 40, 40, 40)
        left_layout.setSpacing(0)

        left_layout.addStretch(2)

        # 左侧 Logo
        left_logo = QLabel()
        left_logo.setFixedSize(80, 80)
        left_logo.setStyleSheet("""
            background: rgba(255, 255, 255, 0.15);
            border-radius: 20px;
            border: none;
        """)
        logo_pixmap = self._create_logo()
        left_logo.setPixmap(logo_pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        left_logo.setAlignment(Qt.AlignCenter)

        logo_container = QHBoxLayout()
        logo_container.addStretch()
        logo_container.addWidget(left_logo)
        logo_container.addStretch()
        left_layout.addLayout(logo_container)
        left_layout.addSpacing(24)

        # 左侧标题
        left_title = QLabel("FlyTest")
        left_title.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: white;
            background: transparent;
        """)
        left_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(left_title)
        left_layout.addSpacing(8)

        # 左侧副标题
        left_subtitle = QLabel("Flytest智能测试平台")
        left_subtitle.setStyleSheet("""
            font-size: 16px;
            color: rgba(255, 255, 255, 0.85);
            background: transparent;
        """)
        left_subtitle.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(left_subtitle)
        left_layout.addSpacing(40)

        # 功能特性列表 - 2列网格布局（使用简写标识，完全兼容）
        features = [
            ("AI", "智能生成"),
            ("DB", "RAG 知识库"),
            ("MCP", "工具调用"),
            ("SK", "Skills 技能库"),
            ("PW", "自动化执行"),
            ("LG", "LangGraph"),
        ]

        features_grid = QGridLayout()
        features_grid.setSpacing(12)
        features_grid.setHorizontalSpacing(16)

        for idx, (icon, text) in enumerate(features):
            row = idx // 2
            col = idx % 2

            feature_widget = QFrame()
            feature_widget.setStyleSheet("""
                QFrame {
                    background: rgba(255, 255, 255, 0.08);
                    border-radius: 10px;
                }
            """)
            feature_widget.setFixedHeight(46)
            feature_widget.setMinimumWidth(145)

            feature_layout = QHBoxLayout(feature_widget)
            feature_layout.setContentsMargins(10, 8, 10, 8)
            feature_layout.setSpacing(8)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet("""
                font-size: 10px;
                font-weight: bold;
                color: rgba(255, 255, 255, 0.95);
                background: rgba(255, 255, 255, 0.18);
                border-radius: 4px;
            """)
            icon_label.setMinimumWidth(32)
            icon_label.setFixedHeight(22)
            icon_label.setAlignment(Qt.AlignCenter)

            text_label = QLabel(text)
            text_label.setStyleSheet("""
                font-size: 12px;
                color: rgba(255, 255, 255, 0.95);
                background: transparent;
            """)

            feature_layout.addWidget(icon_label)
            feature_layout.addWidget(text_label, 1)

            features_grid.addWidget(feature_widget, row, col)

        left_layout.addLayout(features_grid)
        left_layout.addStretch(3)

        main_layout.addWidget(left_panel)

        # ========== 右侧登录表单区域 ==========
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
            }
        """)

        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(50, 40, 50, 40)
        right_layout.setSpacing(0)

        right_layout.addStretch(1)

        # 表单卡片
        form_card = QFrame()
        form_card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 16px;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(80)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 16)
        form_card.setGraphicsEffect(shadow)

        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(32, 24, 32, 24)
        form_layout.setSpacing(0)

        # 选项卡
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: transparent;
                border: none;
                padding: 10px 24px;
                font-size: 15px;
                color: #666;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #1976D2;
                border-bottom: 2px solid #1976D2;
                font-weight: 500;
            }
            QTabBar::tab:hover {
                color: #1976D2;
            }
        """)

        # ========== 登录选项卡 ==========
        login_tab = QWidget()
        login_tab_layout = QVBoxLayout(login_tab)
        login_tab_layout.setContentsMargins(8, 20, 8, 8)
        login_tab_layout.setSpacing(0)

        # 输入框样式
        input_style = """
            QLineEdit {
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 14px 16px;
                font-size: 15px;
                background-color: #fafafa;
                color: #333;
            }
            QLineEdit:focus {
                border-color: #1976D2;
                background-color: white;
            }
            QLineEdit::placeholder {
                color: #bbb;
            }
        """

        # 服务器地址（带图标提示）
        server_container = QFrame()
        server_container.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
            }
            QFrame:focus-within {
                border-color: #1976D2;
                background-color: white;
            }
        """)
        server_container.setFixedHeight(50)
        server_layout = QHBoxLayout(server_container)
        server_layout.setContentsMargins(12, 0, 12, 0)
        server_layout.setSpacing(8)
        
        server_icon = QLabel("◉")
        server_icon.setStyleSheet("font-size: 16px; color: #1976D2; background: transparent; border: none; font-weight: bold;")
        server_icon.setFixedWidth(24)
        server_layout.addWidget(server_icon)
        
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("服务器地址")
        self.api_url_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 15px;
                color: #333;
                padding: 0;
            }
            QLineEdit::placeholder { color: #bbb; }
        """)
        server_layout.addWidget(self.api_url_input)
        login_tab_layout.addWidget(server_container)
        login_tab_layout.addSpacing(14)

        # 用户名（带图标提示）
        user_container = QFrame()
        user_container.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
            }
            QFrame:focus-within {
                border-color: #1976D2;
                background-color: white;
            }
        """)
        user_container.setFixedHeight(50)
        user_layout = QHBoxLayout(user_container)
        user_layout.setContentsMargins(12, 0, 12, 0)
        user_layout.setSpacing(8)
        
        user_icon = QLabel("●")
        user_icon.setStyleSheet("font-size: 14px; color: #1976D2; background: transparent; border: none;")
        user_icon.setFixedWidth(24)
        user_layout.addWidget(user_icon)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        self.username_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 15px;
                color: #333;
                padding: 0;
            }
            QLineEdit::placeholder { color: #bbb; }
        """)
        user_layout.addWidget(self.username_input)
        login_tab_layout.addWidget(user_container)
        login_tab_layout.addSpacing(14)

        # 密码（带图标提示）
        password_container = QFrame()
        password_container.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
            }
            QFrame:focus-within {
                border-color: #1976D2;
                background-color: white;
            }
        """)
        password_container.setFixedHeight(50)
        password_layout = QHBoxLayout(password_container)
        password_layout.setContentsMargins(12, 0, 12, 0)
        password_layout.setSpacing(8)
        
        password_icon = QLabel("◆")
        password_icon.setStyleSheet("font-size: 14px; color: #1976D2; background: transparent; border: none;")
        password_icon.setFixedWidth(24)
        password_layout.addWidget(password_icon)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 15px;
                color: #333;
                padding: 0;
            }
            QLineEdit::placeholder { color: #bbb; }
        """)
        password_layout.addWidget(self.password_input)
        
        # 密码显示/隐藏按钮 - 使用圆形悬停效果
        self._password_visible = False
        self._password_toggle_btn = QPushButton("◎")
        self._password_toggle_btn.setStyleSheet("""
            QPushButton {
                background: #f5f5f5;
                border: none;
                border-radius: 14px;
                font-size: 14px;
                color: #757575;
                padding: 4px;
            }
            QPushButton:hover {
                background: #e3f2fd;
                color: #1976D2;
            }
            QPushButton:pressed {
                background: #bbdefb;
            }
        """)
        self._password_toggle_btn.setFixedSize(28, 28)
        self._password_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._password_toggle_btn.clicked.connect(self._toggle_password_visibility)
        password_layout.addWidget(self._password_toggle_btn)
        
        login_tab_layout.addWidget(password_container)
        login_tab_layout.addSpacing(16)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; background: transparent; font-size: 13px;")
        self.status_label.setFixedHeight(16)
        login_tab_layout.addWidget(self.status_label)
        login_tab_layout.addSpacing(8)

        # 登录按钮
        self.login_btn = QPushButton("登录")
        self.login_btn.setFixedHeight(50)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1E88E5, stop:1 #1565C0);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #42A5F5, stop:1 #1E88E5);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1565C0, stop:1 #0D47A1);
            }
            QPushButton:disabled {
                background: #ccc;
            }
        """)
        self.login_btn.clicked.connect(self._on_login_clicked)
        login_tab_layout.addWidget(self.login_btn)
        login_tab_layout.addStretch()

        self.tab_widget.addTab(login_tab, "登录")

        # ========== 设置选项卡 ==========
        settings_tab = QWidget()
        settings_tab_layout = QVBoxLayout(settings_tab)
        settings_tab_layout.setContentsMargins(8, 20, 8, 8)
        settings_tab_layout.setSpacing(12)

        # 设置项样式
        label_style = "font-size: 13px; color: #666; background: transparent;"
        combo_style = """
            QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px 12px;
                padding-right: 32px;
                font-size: 14px;
                background-color: #fafafa;
                color: #333;
            }
            QComboBox:hover {
                border-color: #bdbdbd;
                background-color: #f5f5f5;
            }
            QComboBox:focus {
                border-color: #1976D2;
                background-color: white;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
                subcontrol-origin: padding;
                subcontrol-position: center right;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QComboBox::drop-down:hover {
                background: #e3f2fd;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM3NTc1NzUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSI2IDkgMTIgMTUgMTggOSIvPjwvc3ZnPg==);
            }
            QComboBox::down-arrow:hover {
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiMxOTc2RDIiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSI2IDkgMTIgMTUgMTggOSIvPjwvc3ZnPg==);
            }
            QComboBox QAbstractItemView {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
                selection-background-color: #e3f2fd;
                selection-color: #1976D2;
                padding: 4px;
            }
        """
        checkbox_style = """
            QCheckBox {
                font-size: 14px;
                color: #333;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #d0d0d0;
                background: #fafafa;
            }
            QCheckBox::indicator:hover {
                border-color: #1976D2;
                background: #e3f2fd;
            }
            QCheckBox::indicator:checked {
                background: #1976D2;
                border-color: #1976D2;
            }
        """
        spinbox_style = """
            QSpinBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 8px 12px;
                padding-right: 36px;
                font-size: 14px;
                background-color: #fafafa;
                color: #333;
            }
            QSpinBox:hover {
                border-color: #bdbdbd;
            }
            QSpinBox:focus {
                border-color: #1976D2;
                background-color: white;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 24px;
                height: 18px;
                background: #f5f5f5;
                border: none;
                border-left: 1px solid #e0e0e0;
                border-top-right-radius: 7px;
            }
            QSpinBox::up-button:hover {
                background: #e3f2fd;
            }
            QSpinBox::up-button:pressed {
                background: #bbdefb;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 24px;
                height: 18px;
                background: #f5f5f5;
                border: none;
                border-left: 1px solid #e0e0e0;
                border-bottom-right-radius: 7px;
            }
            QSpinBox::down-button:hover {
                background: #e3f2fd;
            }
            QSpinBox::down-button:pressed {
                background: #bbdefb;
            }
            QSpinBox::up-arrow {
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 5px solid #666;
            }
            QSpinBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #666;
            }
        """

        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #d0d0d0;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        scroll_layout.setSpacing(10)

        # 输入框样式（用于设置页）
        settings_input_style = """
            QLineEdit {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                background-color: #fafafa;
                color: #333;
            }
            QLineEdit:focus {
                border-color: #1976D2;
                background-color: white;
            }
            QLineEdit::placeholder {
                color: #bbb;
            }
        """

        # ===== 执行器设置 =====
        actuator_section = QLabel("执行器设置")
        actuator_section.setStyleSheet("font-size: 14px; font-weight: 500; color: #333; background: transparent;")
        scroll_layout.addWidget(actuator_section)

        # 执行器名称
        actuator_name_label = QLabel("执行器名称（留空则自动生成）")
        actuator_name_label.setStyleSheet(label_style)
        scroll_layout.addWidget(actuator_name_label)

        self.actuator_name_input = QLineEdit()
        self.actuator_name_input.setPlaceholderText("例如: my-actuator")
        self.actuator_name_input.setStyleSheet(settings_input_style)
        self.actuator_name_input.setFixedHeight(40)
        scroll_layout.addWidget(self.actuator_name_input)

        scroll_layout.addSpacing(8)

        # ===== 浏览器设置 =====
        browser_section = QLabel("浏览器设置")
        browser_section.setStyleSheet("font-size: 14px; font-weight: 500; color: #333; background: transparent;")
        scroll_layout.addWidget(browser_section)

        # 浏览器类型
        browser_label = QLabel("浏览器类型")
        browser_label.setStyleSheet(label_style)
        scroll_layout.addWidget(browser_label)

        self.browser_type_combo = QComboBox()
        self.browser_type_combo.addItems(["chromium", "firefox", "webkit"])
        self.browser_type_combo.setStyleSheet(combo_style)
        self.browser_type_combo.setFixedHeight(40)
        scroll_layout.addWidget(self.browser_type_combo)

        # 无头模式
        self.headless_checkbox = QCheckBox("无头模式（后台运行，无界面）")
        self.headless_checkbox.setStyleSheet(checkbox_style)
        scroll_layout.addWidget(self.headless_checkbox)

        # 持久化浏览器
        self.persistent_checkbox = QCheckBox("持久化浏览器上下文")
        self.persistent_checkbox.setStyleSheet(checkbox_style)
        self.persistent_checkbox.setChecked(True)
        scroll_layout.addWidget(self.persistent_checkbox)

        # 启动超时
        timeout_label = QLabel("启动超时（秒）")
        timeout_label.setStyleSheet(label_style)
        scroll_layout.addWidget(timeout_label)

        self.launch_timeout_spin = QSpinBox()
        self.launch_timeout_spin.setRange(10, 120)
        self.launch_timeout_spin.setValue(30)
        self.launch_timeout_spin.setStyleSheet(spinbox_style)
        self.launch_timeout_spin.setFixedHeight(40)
        scroll_layout.addWidget(self.launch_timeout_spin)

        # 操作超时
        action_timeout_label = QLabel("操作超时（秒）")
        action_timeout_label.setStyleSheet(label_style)
        scroll_layout.addWidget(action_timeout_label)

        self.action_timeout_spin = QSpinBox()
        self.action_timeout_spin.setRange(5, 60)
        self.action_timeout_spin.setValue(30)
        self.action_timeout_spin.setStyleSheet(spinbox_style)
        self.action_timeout_spin.setFixedHeight(40)
        scroll_layout.addWidget(self.action_timeout_spin)

        scroll_layout.addSpacing(8)

        # ===== 执行设置 =====
        exec_section = QLabel("执行设置")
        exec_section.setStyleSheet("font-size: 14px; font-weight: 500; color: #333; background: transparent;")
        scroll_layout.addWidget(exec_section)

        # 失败重试次数
        retry_label = QLabel("失败重试次数")
        retry_label.setStyleSheet(label_style)
        scroll_layout.addWidget(retry_label)

        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(0, 10)
        self.retry_count_spin.setValue(3)
        self.retry_count_spin.setStyleSheet(spinbox_style)
        self.retry_count_spin.setFixedHeight(40)
        scroll_layout.addWidget(self.retry_count_spin)

        # 步骤间隔时间
        step_interval_label = QLabel("步骤间隔（毫秒）")
        step_interval_label.setStyleSheet(label_style)
        scroll_layout.addWidget(step_interval_label)

        self.step_interval_spin = QSpinBox()
        self.step_interval_spin.setRange(0, 5000)
        self.step_interval_spin.setValue(500)
        self.step_interval_spin.setSingleStep(100)
        self.step_interval_spin.setStyleSheet(spinbox_style)
        self.step_interval_spin.setFixedHeight(40)
        scroll_layout.addWidget(self.step_interval_spin)

        # 批量执行最大并发数
        max_concurrent_label = QLabel("批量执行并发数")
        max_concurrent_label.setStyleSheet(label_style)
        scroll_layout.addWidget(max_concurrent_label)

        self.max_concurrent_spin = QSpinBox()
        self.max_concurrent_spin.setRange(1, 10)
        self.max_concurrent_spin.setValue(3)
        self.max_concurrent_spin.setStyleSheet(spinbox_style)
        self.max_concurrent_spin.setFixedHeight(40)
        scroll_layout.addWidget(self.max_concurrent_spin)

        scroll_layout.addSpacing(8)

        # ===== Trace 设置 =====
        trace_section = QLabel("Trace 设置")
        trace_section.setStyleSheet("font-size: 14px; font-weight: 500; color: #333; background: transparent;")
        scroll_layout.addWidget(trace_section)

        # Trace 开关
        self.trace_checkbox = QCheckBox("启用 Trace 录制")
        self.trace_checkbox.setStyleSheet(checkbox_style)
        self.trace_checkbox.setChecked(True)
        scroll_layout.addWidget(self.trace_checkbox)

        # Trace 截图
        self.trace_screenshots_checkbox = QCheckBox("记录截图")
        self.trace_screenshots_checkbox.setStyleSheet(checkbox_style)
        self.trace_screenshots_checkbox.setChecked(True)
        scroll_layout.addWidget(self.trace_screenshots_checkbox)

        # Trace 快照
        self.trace_snapshots_checkbox = QCheckBox("记录 DOM 快照")
        self.trace_snapshots_checkbox.setStyleSheet(checkbox_style)
        self.trace_snapshots_checkbox.setChecked(True)
        scroll_layout.addWidget(self.trace_snapshots_checkbox)

        # Trace 源代码
        self.trace_sources_checkbox = QCheckBox("记录源代码")
        self.trace_sources_checkbox.setStyleSheet(checkbox_style)
        self.trace_sources_checkbox.setChecked(False)
        scroll_layout.addWidget(self.trace_sources_checkbox)

        scroll_layout.addSpacing(8)

        # ===== 日志设置 =====
        log_section = QLabel("日志设置")
        log_section.setStyleSheet("font-size: 14px; font-weight: 500; color: #333; background: transparent;")
        scroll_layout.addWidget(log_section)

        # 日志级别
        log_level_label = QLabel("日志级别")
        log_level_label.setStyleSheet(label_style)
        scroll_layout.addWidget(log_level_label)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        self.log_level_combo.setStyleSheet(combo_style)
        self.log_level_combo.setFixedHeight(40)
        scroll_layout.addWidget(self.log_level_combo)

        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        settings_tab_layout.addWidget(scroll_area)

        self.tab_widget.addTab(settings_tab, "设置")

        form_layout.addWidget(self.tab_widget)

        right_layout.addWidget(form_card)
        right_layout.addStretch(1)

        # 隐藏取消按钮（兼容性）
        self.cancel_btn = QPushButton()
        self.cancel_btn.hide()

        main_layout.addWidget(right_panel)

        # 回车键登录
        self.password_input.returnPressed.connect(self._on_login_clicked)

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        self.reject()
        event.accept()

    def reject(self):
        """处理取消/关闭操作"""
        super().reject()

    def _toggle_password_visibility(self):
        """切换密码可见性"""
        self._password_visible = not self._password_visible
        if self._password_visible:
            self.password_input.setEchoMode(QLineEdit.Normal)
            self._password_toggle_btn.setText("●")  # 实心圆 - 密码可见
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
            self._password_toggle_btn.setText("◎")  # 双圆 - 密码隐藏

    def _get_window_icon(self) -> Optional[QIcon]:
        """获取窗口图标"""
        import sys
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).parent.parent
        
        icon_paths = [
            base_path / "data" / "FlyTest.png",
            base_path / "FlyTest.png",
            base_path.parent / "FlyTest_Vue" / "public" / "FlyTest.png",
        ]
        
        for icon_path in icon_paths:
            if icon_path.exists():
                return QIcon(str(icon_path))
        return None

    def _create_logo(self) -> QPixmap:
        """创建 Logo - 尝试加载图片，失败则使用默认绘制"""
        # 尝试加载项目 logo 图片
        logo_paths = [
            Path(__file__).parent.parent / "data" / "FlyTest.png",
            Path(__file__).parent.parent.parent / "FlyTest_Vue" / "public" / "FlyTest.png",
            Path(__file__).parent.parent / "FlyTest.png",
        ]
        
        for logo_path in logo_paths:
            if logo_path.exists():
                pixmap = QPixmap(str(logo_path))
                if not pixmap.isNull():
                    return pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # 如果找不到图片，使用默认绘制
        pixmap = QPixmap(56, 56)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制箭头形状
        from PySide6.QtGui import QPainterPath, QBrush

        path = QPainterPath()
        path.moveTo(8, 14)
        path.lineTo(30, 28)
        path.lineTo(8, 42)
        path.lineTo(18, 28)
        path.closeSubpath()
        painter.setBrush(QBrush(QColor("#0096c7")))
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)

        path2 = QPainterPath()
        path2.moveTo(24, 14)
        path2.lineTo(46, 28)
        path2.lineTo(24, 42)
        path2.lineTo(34, 28)
        path2.closeSubpath()
        painter.setBrush(QBrush(QColor("#48cae4")))
        painter.drawPath(path2)

        painter.end()
        return pixmap
    
    def _load_saved_credentials(self):
        """加载保存的凭证和设置"""
        server = self._config.get('server', {})
        self.api_url_input.setText(server.get('api_url', 'http://localhost:8000'))
        self.username_input.setText(server.get('api_username', ''))
        self.password_input.setText(server.get('api_password', ''))
        
        # 加载执行器设置
        actuator = self._config.get('actuator', {})
        self.actuator_name_input.setText(actuator.get('name', ''))
        
        # 加载浏览器设置
        browser = self._config.get('browser', {})
        browser_type = browser.get('browser_type', 'chromium')
        index = self.browser_type_combo.findText(browser_type)
        if index >= 0:
            self.browser_type_combo.setCurrentIndex(index)
        self.headless_checkbox.setChecked(browser.get('headless', False))
        self.persistent_checkbox.setChecked(browser.get('persistent', True))
        self.launch_timeout_spin.setValue(browser.get('launch_timeout', 30))
        self.action_timeout_spin.setValue(browser.get('action_timeout', 30))
        
        # 加载执行设置
        execution = self._config.get('execution', {})
        self.retry_count_spin.setValue(execution.get('retry_count', 3))
        self.step_interval_spin.setValue(execution.get('step_interval', 500))
        self.max_concurrent_spin.setValue(execution.get('max_concurrent', 3))
        
        # 加载 Trace 设置
        trace = self._config.get('trace', {})
        self.trace_checkbox.setChecked(trace.get('enabled', True))
        self.trace_screenshots_checkbox.setChecked(trace.get('screenshots', True))
        self.trace_snapshots_checkbox.setChecked(trace.get('snapshots', True))
        self.trace_sources_checkbox.setChecked(trace.get('sources', False))
        
        # 加载日志设置
        logging_cfg = self._config.get('logging', {})
        log_level = logging_cfg.get('level', 'INFO')
        index = self.log_level_combo.findText(log_level)
        if index >= 0:
            self.log_level_combo.setCurrentIndex(index)
    
    def _on_login_clicked(self):
        """登录按钮点击处理"""
        api_url = self.api_url_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not api_url:
            self._show_error("请输入服务器地址")
            return
        if not username:
            self._show_error("请输入用户名")
            return
        if not password:
            self._show_error("请输入密码")
            return
        
        self._set_loading(True)
        self.status_label.setText("正在登录...")
        self.status_label.setStyleSheet("color: #1890ff;")
        
        # 启动登录工作线程
        self._login_worker = LoginWorker(api_url, username, password, self)
        self._login_worker.login_success.connect(self._on_login_success)
        self._login_worker.login_failed.connect(self._on_login_failed)
        self._login_worker.start()
    
    def _on_login_success(self, access_token: str, refresh_token: str):
        """登录成功处理"""
        self._access_token = access_token
        self._refresh_token = refresh_token
        
        # 更新服务器配置
        if 'server' not in self._config:
            self._config['server'] = {}
        self._config['server']['api_url'] = self.api_url_input.text().strip()
        self._config['server']['api_username'] = self.username_input.text().strip()
        self._config['server']['api_password'] = self.password_input.text()
        
        # 更新执行器配置
        if 'actuator' not in self._config:
            self._config['actuator'] = {}
        actuator_name = self.actuator_name_input.text().strip()
        if actuator_name:
            self._config['actuator']['name'] = actuator_name
        elif 'name' in self._config['actuator']:
            del self._config['actuator']['name']
        
        # 更新浏览器配置
        if 'browser' not in self._config:
            self._config['browser'] = {}
        self._config['browser']['browser_type'] = self.browser_type_combo.currentText()
        self._config['browser']['headless'] = self.headless_checkbox.isChecked()
        self._config['browser']['persistent'] = self.persistent_checkbox.isChecked()
        self._config['browser']['launch_timeout'] = self.launch_timeout_spin.value()
        self._config['browser']['action_timeout'] = self.action_timeout_spin.value()
        
        # 更新执行配置
        if 'execution' not in self._config:
            self._config['execution'] = {}
        self._config['execution']['retry_count'] = self.retry_count_spin.value()
        self._config['execution']['step_interval'] = self.step_interval_spin.value()
        self._config['execution']['max_concurrent'] = self.max_concurrent_spin.value()
        
        # 更新 Trace 配置
        if 'trace' not in self._config:
            self._config['trace'] = {}
        self._config['trace']['enabled'] = self.trace_checkbox.isChecked()
        self._config['trace']['screenshots'] = self.trace_screenshots_checkbox.isChecked()
        self._config['trace']['snapshots'] = self.trace_snapshots_checkbox.isChecked()
        self._config['trace']['sources'] = self.trace_sources_checkbox.isChecked()
        
        # 更新日志配置
        if 'logging' not in self._config:
            self._config['logging'] = {}
        self._config['logging']['level'] = self.log_level_combo.currentText()
        
        self._save_config()
        
        self.status_label.setText("登录成功！")
        self.status_label.setStyleSheet("color: #52c41a;")
        
        self.accept()
    
    def _on_login_failed(self, error: str):
        """登录失败处理"""
        self._set_loading(False)
        self.status_label.setText(error)
        self.status_label.setStyleSheet("color: #ff4d4f;")
    
    def _set_loading(self, loading: bool):
        """设置加载状态"""
        self.login_btn.setEnabled(not loading)
        self.api_url_input.setEnabled(not loading)
        self.username_input.setEnabled(not loading)
        self.password_input.setEnabled(not loading)
    
    def _show_error(self, message: str):
        """显示错误信息"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #ff4d4f;")
    
    @property
    def access_token(self) -> Optional[str]:
        """获取登录成功后的 access token"""
        return self._access_token
    
    @property
    def refresh_token(self) -> Optional[str]:
        """获取登录成功后的 refresh token"""
        return self._refresh_token
    
    @property
    def api_url(self) -> str:
        """获取服务器地址"""
        return self.api_url_input.text().strip()
    
    @property
    def actuator_name(self) -> str:
        """获取执行器名称"""
        return self.actuator_name_input.text().strip()
    
    @property
    def username(self) -> str:
        """获取用户名"""
        return self.username_input.text().strip()
    
    @property
    def password(self) -> str:
        """获取密码"""
        return self.password_input.text()
    
    @property
    def browser_type(self) -> str:
        """获取浏览器类型"""
        return self.browser_type_combo.currentText()
    
    @property
    def headless(self) -> bool:
        """获取无头模式设置"""
        return self.headless_checkbox.isChecked()
    
    @property
    def persistent(self) -> bool:
        """获取持久化浏览器设置"""
        return self.persistent_checkbox.isChecked()
    
    @property
    def trace_enabled(self) -> bool:
        """获取 Trace 启用设置"""
        return self.trace_checkbox.isChecked()
    
    @property
    def trace_screenshots(self) -> bool:
        """获取 Trace 截图设置"""
        return self.trace_screenshots_checkbox.isChecked()
    
    @property
    def trace_snapshots(self) -> bool:
        """获取 Trace 快照设置"""
        return self.trace_snapshots_checkbox.isChecked()
    
    @property
    def trace_sources(self) -> bool:
        """获取 Trace 源代码设置"""
        return self.trace_sources_checkbox.isChecked()
    
    @property
    def launch_timeout(self) -> int:
        """获取启动超时设置"""
        return self.launch_timeout_spin.value()
    
    @property
    def action_timeout(self) -> int:
        """获取操作超时设置"""
        return self.action_timeout_spin.value()
    
    @property
    def retry_count(self) -> int:
        """获取失败重试次数"""
        return self.retry_count_spin.value()
    
    @property
    def step_interval(self) -> int:
        """获取步骤间隔（毫秒）"""
        return self.step_interval_spin.value()
    
    @property
    def max_concurrent(self) -> int:
        """获取批量执行最大并发数"""
        return self.max_concurrent_spin.value()
    
    @property
    def log_level(self) -> str:
        """获取日志级别"""
        return self.log_level_combo.currentText()


def show_login_dialog(config_path: str = "config.toml") -> Optional[dict]:
    """
    显示登录对话框
    
    Returns:
        成功返回包含登录信息和配置的字典
        取消或失败返回 None
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    login_window = LoginWindow(config_path)
    result = login_window.exec()
    
    if result == QDialog.Accepted and login_window.access_token:
        return {
            'access_token': login_window.access_token,
            'refresh_token': login_window.refresh_token,
            'api_url': login_window.api_url,
            'actuator_name': login_window.actuator_name,
            'username': login_window.username,
            'password': login_window.password,
            'browser_type': login_window.browser_type,
            'headless': login_window.headless,
            'persistent': login_window.persistent,
            'trace_enabled': login_window.trace_enabled,
            'trace_screenshots': login_window.trace_screenshots,
            'trace_snapshots': login_window.trace_snapshots,
            'trace_sources': login_window.trace_sources,
            'launch_timeout': login_window.launch_timeout,
            'action_timeout': login_window.action_timeout,
            'retry_count': login_window.retry_count,
            'step_interval': login_window.step_interval,
            'max_concurrent': login_window.max_concurrent,
            'log_level': login_window.log_level,
        }
    return None


if __name__ == "__main__":
    # 独立测试
    result = show_login_dialog()
    if result:
        print(f"登录成功: {result['username']} @ {result['api_url']}")
        print(f"执行器名称: {result['actuator_name'] or '(自动生成)'}")
        print(f"Token: {result['access_token'][:20]}...")
        print(f"浏览器: {result['browser_type']}, 无头: {result['headless']}, 持久化: {result['persistent']}")
        print(f"Trace: {result['trace_enabled']}, 截图: {result['trace_screenshots']}, 快照: {result['trace_snapshots']}")
        print(f"超时: {result['launch_timeout']}s/{result['action_timeout']}s, 并发: {result['max_concurrent']}")
        print(f"重试: {result['retry_count']}, 步骤间隔: {result['step_interval']}ms, 日志: {result['log_level']}")
    else:
        print("登录取消或失败")
