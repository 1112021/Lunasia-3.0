# -*- coding: utf-8 -*-
"""
UI对话框模块
包含设置、记忆系统、MCP工具等对话框
"""

import os
import json
import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
                             QPushButton, QLabel, QComboBox, QSplitter, QListWidget,
                             QGroupBox, QFormLayout, QMessageBox, QInputDialog, 
                             QFileDialog, QProgressBar, QListWidgetItem, QTabWidget,
                             QSlider, QCheckBox, QScrollArea, QWidget, QProgressDialog, QSpinBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

from config import save_config
from utils import scan_windows_apps
from memory_lake import MemoryLake
from mcp_server import LocalMCPServer


class _NoWheelComboBox(QComboBox):
    """设置中使用的下拉框：滚轮不改变选项，避免误触"""
    def wheelEvent(self, event):
        event.ignore()


class _NoWheelSpinBox(QSpinBox):
    """设置中使用的数字框：滚轮不改变数值，避免误触"""
    def wheelEvent(self, event):
        event.ignore()


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, config, parent=None, transparency_callback=None):
        super().__init__(parent)
        self.config = config
        self.transparency_callback = transparency_callback  # 透明度更新回调
        self.setWindowTitle("AI助手设置")
        self.setGeometry(300, 300, 620, 800)  # 设置合适的窗口大小，宽度增加20px以容纳滚动条
        
        # 设置窗口大小策略
        from PyQt5.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMinimumWidth(620)  # 设置最小宽度
        self.setMaximumWidth(620)  # 设置最大宽度，与最小宽度相同，锁定宽度
        self.setMinimumHeight(800)  # 设置固定高度
        self.setMaximumHeight(800)  # 设置最大高度，锁定高度

        # 设置图标
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))

        self.init_ui()

        # 设置里的下拉框/数字框已使用 _NoWheelComboBox / _NoWheelSpinBox，滚轮不会改变选项

    def create_password_input_with_toggle(self, line_edit, placeholder=""):
        """创建带显示/隐藏切换按钮的密码输入框"""
        container = QHBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)

        line_edit.setEchoMode(QLineEdit.Password)
        if placeholder:
            line_edit.setPlaceholderText(placeholder)

        toggle_btn = QPushButton("显示")
        toggle_btn.setFixedWidth(50)
        toggle_btn.setToolTip("点击切换显示/隐藏")
        toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #45475a;
                color: #cdd6f4;
                border: none;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
        """)
        toggle_btn.is_visible = False

        def toggle_visibility():
            if toggle_btn.is_visible:
                line_edit.setEchoMode(QLineEdit.Password)
                toggle_btn.setText("显示")
                toggle_btn.is_visible = False
            else:
                line_edit.setEchoMode(QLineEdit.Normal)
                toggle_btn.setText("隐藏")
                toggle_btn.is_visible = True

        toggle_btn.clicked.connect(toggle_visibility)
        container.addWidget(line_edit)
        container.addWidget(toggle_btn)

        wrapper = QWidget()
        wrapper.setLayout(container)
        return wrapper

    def init_ui(self):
        """初始化UI"""
        # 创建主布局
        main_layout = QVBoxLayout()
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)

        # API设置
        api_group = QGroupBox("API设置")
        api_layout = QFormLayout()

        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setText(self.config.get("openai_key", ""))
        api_layout.addRow("OpenAI API密钥:", self.create_password_input_with_toggle(
            self.openai_key_edit, "输入OpenAI API密钥"))

        self.deepseek_key_edit = QLineEdit()
        self.deepseek_key_edit.setText(self.config.get("deepseek_key", ""))
        api_layout.addRow("DeepSeek API密钥:", self.create_password_input_with_toggle(
            self.deepseek_key_edit, "输入DeepSeek API密钥"))

        self.qwen3vl_plus_key_edit = QLineEdit()
        self.qwen3vl_plus_key_edit.setText(self.config.get("qwen3vl_plus_key", ""))
        self.qwen3vl_plus_key_edit.setToolTip("Qwen3VL-Plus是通义千问的多模态模型，用于图片理解和分析")
        api_layout.addRow("Qwen3VL-Plus API密钥:", self.create_password_input_with_toggle(
            self.qwen3vl_plus_key_edit, "输入Qwen3VL-Plus API密钥（用于图片分析）"))

        self.weather_key_edit = QLineEdit()
        self.weather_key_edit.setText(self.config.get("heweather_key", ""))
        api_layout.addRow("和风天气API密钥:", self.create_password_input_with_toggle(
            self.weather_key_edit, "输入和风天气API密钥"))

        self.amap_key_edit = QLineEdit()
        self.amap_key_edit.setText(self.config.get("amap_key", ""))
        api_layout.addRow("高德地图API密钥:", self.create_password_input_with_toggle(
            self.amap_key_edit, "输入高德地图API密钥"))

        self.dashscope_key_edit = QLineEdit()
        self.dashscope_key_edit.setText(self.config.get("dashscope_key", ""))
        self.dashscope_key_edit.setToolTip("用于语音识别（Paraformer 8k-v2），可与通义/百炼 API Key 共用")
        api_layout.addRow("语音识别 API 密钥 (DashScope):", self.create_password_input_with_toggle(
            self.dashscope_key_edit, "输入 DashScope API 密钥（语音输入）"))

        self.voice_auto_send_checkbox = QCheckBox("语音识别结束后自动发送")
        self.voice_auto_send_checkbox.setChecked(self.config.get("voice_auto_send", False))
        self.voice_auto_send_checkbox.setToolTip("开启后，语音识别得到的文字会填入输入框并立即发送")
        api_layout.addRow("", self.voice_auto_send_checkbox)

        # 天气数据来源设置
        self.weather_source_combo = _NoWheelComboBox()
        self.weather_source_combo.addItems(["和风天气API", "高德地图API"])
        current_source = self.config.get("weather_source", "和风天气API")
        index = self.weather_source_combo.findText(current_source)
        if index >= 0:
            self.weather_source_combo.setCurrentIndex(index)
        api_layout.addRow("天气数据来源:", self.weather_source_combo)

        api_group.setLayout(api_layout)

        # 浏览器设置
        browser_group = QGroupBox("浏览器设置")
        browser_layout = QFormLayout()

        self.default_browser_combo = _NoWheelComboBox()
        self.default_browser_combo.addItems(["默认浏览器", "chrome", "firefox", "edge", "opera", "safari"])
        current_browser = self.config.get("default_browser", "")
        if current_browser:
            index = self.default_browser_combo.findText(current_browser)
            if index >= 0:
                self.default_browser_combo.setCurrentIndex(index)
        browser_layout.addRow("默认浏览器:", self.default_browser_combo)

        self.default_search_engine_combo = _NoWheelComboBox()
        self.default_search_engine_combo.addItems(["baidu", "google", "bing", "sogou", "360"])
        current_engine = self.config.get("default_search_engine", "baidu")
        index = self.default_search_engine_combo.findText(current_engine)
        if index >= 0:
            self.default_search_engine_combo.setCurrentIndex(index)
        browser_layout.addRow("默认搜索引擎:", self.default_search_engine_combo)
        
        browser_group.setLayout(browser_layout)
        
        # Playwright 自动化配置（移到新的组）
        playwright_group = QGroupBox("Playwright 自动化配置")
        playwright_layout = QFormLayout()
        
        # Playwright 启动模式
        self.playwright_mode_combo = _NoWheelComboBox()
        self.playwright_mode_combo.addItems(["launch", "connect", "persistent"])
        self.playwright_mode_combo.setToolTip(
            "launch: 常规启动（默认）\n"
            "connect: 连接已有浏览器（调试）\n"
            "persistent: 持久化上下文（保存登录状态）"
        )
        current_mode = self.config.get("playwright_mode", "launch")
        index = self.playwright_mode_combo.findText(current_mode)
        if index >= 0:
            self.playwright_mode_combo.setCurrentIndex(index)
        playwright_layout.addRow("启动模式:", self.playwright_mode_combo)
        
        # 慢速模式
        self.playwright_slow_mo_spinbox = _NoWheelSpinBox()
        self.playwright_slow_mo_spinbox.setRange(0, 5000)
        self.playwright_slow_mo_spinbox.setSuffix(" ms")
        self.playwright_slow_mo_spinbox.setValue(self.config.get("playwright_slow_mo", 0))
        self.playwright_slow_mo_spinbox.setToolTip("每个操作的延迟时间（0=不延迟，100-500=调试）")
        playwright_layout.addRow("慢速模式:", self.playwright_slow_mo_spinbox)
        
        # CDP连接地址和测试按钮
        cdp_layout = QHBoxLayout()
        self.playwright_cdp_url_input = QLineEdit()
        self.playwright_cdp_url_input.setText(self.config.get("playwright_cdp_url", "http://localhost:9222"))
        self.playwright_cdp_url_input.setPlaceholderText("http://localhost:9222")
        self.playwright_cdp_url_input.setToolTip("连接模式下的浏览器调试地址")
        cdp_layout.addWidget(self.playwright_cdp_url_input)
        
        self.test_cdp_button = QPushButton("测试连接")
        self.test_cdp_button.setMaximumWidth(80)
        self.test_cdp_button.setToolTip("测试CDP调试端口是否可用")
        self.test_cdp_button.clicked.connect(self.test_cdp_connection)
        cdp_layout.addWidget(self.test_cdp_button)
        
        playwright_layout.addRow("CDP地址:", cdp_layout)
        
        # 用户数据目录
        self.playwright_user_data_dir_input = QLineEdit()
        self.playwright_user_data_dir_input.setText(self.config.get("playwright_user_data_dir", ""))
        self.playwright_user_data_dir_input.setPlaceholderText("留空使用默认路径")
        self.playwright_user_data_dir_input.setToolTip("持久化模式下的数据保存路径")
        playwright_layout.addRow("数据目录:", self.playwright_user_data_dir_input)

        playwright_group.setLayout(playwright_layout)

        # 模型设置
        model_group = QGroupBox("AI模型设置")
        model_layout = QVBoxLayout()  # 改用垂直布局以便更好地组织

        # LLM提供商选择（使用更明显的标签）
        provider_label = QLabel("🤖 <b>AI提供商选择</b>")
        model_layout.addWidget(provider_label)
        
        provider_form = QFormLayout()
        
        # 本地/云端选择
        self.llm_type_combo = _NoWheelComboBox()
        self.llm_type_combo.addItems(["云端API", "本地模型"])
        current_provider = self.config.get("llm_provider", "DeepSeek")
        # 根据当前配置设置本地/云端
        if current_provider == "Ollama":
            self.llm_type_combo.setCurrentText("本地模型")
        else:
            self.llm_type_combo.setCurrentText("云端API")
        self.llm_type_combo.currentTextChanged.connect(self.on_llm_type_changed)
        self.llm_type_combo.setToolTip("选择使用云端API还是本地Ollama模型")
        provider_form.addRow("类型:", self.llm_type_combo)
        
        # 云端提供商选择（只在选择云端时显示）
        self.cloud_provider_combo = _NoWheelComboBox()
        self.cloud_provider_combo.addItems(["DeepSeek", "OpenAI"])
        if current_provider in ["DeepSeek", "OpenAI"]:
            self.cloud_provider_combo.setCurrentText(current_provider)
        else:
            self.cloud_provider_combo.setCurrentText("DeepSeek")
        self.cloud_provider_combo.setToolTip("选择具体的云端API提供商")
        self.cloud_provider_combo.currentTextChanged.connect(self.on_cloud_provider_changed)
        provider_form.addRow("云端提供商:", self.cloud_provider_combo)
        self.cloud_provider_combo_label = provider_form.labelForField(self.cloud_provider_combo)
        
        model_layout.addLayout(provider_form)

        # Ollama配置（本地模型）
        ollama_label = QLabel("📦 <b>Ollama本地模型配置</b>")
        self.ollama_label = ollama_label
        model_layout.addWidget(ollama_label)
        
        ollama_form = QFormLayout()
        self.ollama_url_edit = QLineEdit()
        self.ollama_url_edit.setText(self.config.get("ollama_url", "http://localhost:11434"))
        self.ollama_url_edit.setPlaceholderText("http://localhost:11434")
        self.ollama_url_edit.setToolTip("Ollama服务器地址，默认为本地11434端口")
        ollama_form.addRow("服务地址:", self.ollama_url_edit)

        # 模型选择框（从本地扫描）
        ollama_model_layout = QHBoxLayout()
        self.ollama_model_combo = _NoWheelComboBox()
        self.ollama_model_combo.setEditable(True)  # 允许手动输入
        self.ollama_model_combo.setToolTip("从本地Ollama扫描到的模型列表，也可以手动输入")
        ollama_model_layout.addWidget(self.ollama_model_combo, 1)
        
        # 刷新按钮
        self.refresh_ollama_btn = QPushButton("🔄 刷新")
        self.refresh_ollama_btn.setFixedWidth(80)
        self.refresh_ollama_btn.setToolTip("重新扫描本地Ollama模型")
        self.refresh_ollama_btn.clicked.connect(self.refresh_ollama_models)
        ollama_model_layout.addWidget(self.refresh_ollama_btn)
        
        ollama_form.addRow("模型名称:", ollama_model_layout)
        self.ollama_model_layout_widget = ollama_model_layout
        self.ollama_form = ollama_form
        model_layout.addLayout(ollama_form)
        
        # 初始化加载Ollama模型列表
        self.refresh_ollama_models()

        # 云端API配置
        cloud_label = QLabel("☁️ <b>云端API配置</b>")
        self.cloud_label = cloud_label
        model_layout.addWidget(cloud_label)
        
        cloud_form = QFormLayout()
        self.chat_model_combo = _NoWheelComboBox()
        self.chat_model_combo.addItems(["deepseek-chat", "deepseek-coder", "deepseek-reasoner", "gpt-4-turbo", "gpt-3.5-turbo"])
        self.chat_model_combo.setCurrentText(self.config.get("selected_model", "deepseek-chat"))
        self.chat_model_combo.setToolTip("云端API使用的模型")
        cloud_form.addRow("主对话模型:", self.chat_model_combo)

        # 识底深湖模型选择
        self.memory_model_combo = _NoWheelComboBox()
        self.memory_model_combo.addItems(["deepseek-chat", "deepseek-coder", "deepseek-reasoner", "gpt-4-turbo", "gpt-3.5-turbo"])
        self.memory_model_combo.setCurrentText(self.config.get("memory_summary_model", "deepseek-reasoner"))
        self.memory_model_combo.setToolTip("识底深湖记忆总结使用的模型")
        cloud_form.addRow("识底深湖模型:", self.memory_model_combo)
        self.cloud_form = cloud_form
        model_layout.addLayout(cloud_form)

        # 根据当前提供商显示/隐藏相关字段
        self.on_llm_type_changed(self.llm_type_combo.currentText())

        # 通用设置（使用FormLayout）
        general_label = QLabel("⚙️ <b>通用设置</b>")
        model_layout.addWidget(general_label)
        
        general_form = QFormLayout()

        # AI Token数设置
        self.max_tokens_edit = QLineEdit()
        max_tokens = self.config.get("max_tokens", "1000")
        self.max_tokens_edit.setText(str(max_tokens))
        self.max_tokens_edit.setPlaceholderText("输入最大token数，0表示无限制")
        general_form.addRow("最大Token数:", self.max_tokens_edit)

        # 联网搜索设置
        self.enable_web_search_checkbox = QCheckBox("启用联网搜索功能")
        current_search_status = self.config.get("enable_web_search", True)
        self.enable_web_search_checkbox.setChecked(current_search_status)
        print(f"🔍 [设置对话框初始化] 从配置加载 enable_web_search = {current_search_status}")
        
        # 添加状态变化监听，方便调试
        self.enable_web_search_checkbox.stateChanged.connect(
            lambda state: print(f"🔄 [复选框状态变化] enable_web_search: {state == 2} (状态码: {state})")
        )
        
        general_form.addRow("联网搜索:", self.enable_web_search_checkbox)
        
        # 搜索方式选择
        self.search_method_combo = _NoWheelComboBox()
        self.search_method_combo.addItems(["DuckDuckGo", "Playwright"])
        current_method = self.config.get("search_method", "Playwright")
        index = self.search_method_combo.findText(current_method)
        if index >= 0:
            self.search_method_combo.setCurrentIndex(index)
        general_form.addRow("搜索方式:", self.search_method_combo)
        
        # 搜索问题数量设置
        self.max_search_questions_edit = QLineEdit()
        max_search_questions = self.config.get("max_search_questions", 3)
        self.max_search_questions_edit.setText(str(max_search_questions))
        self.max_search_questions_edit.setPlaceholderText("最多生成的搜索问题数量（1-6）")
        general_form.addRow("最大搜索问题数:", self.max_search_questions_edit)
        
        # 搜索结果数量设置
        self.max_search_results_edit = QLineEdit()
        max_search_results = self.config.get("max_search_results", 12)
        self.max_search_results_edit.setText(str(max_search_results))
        self.max_search_results_edit.setPlaceholderText("每次搜索获取的网页数量")
        general_form.addRow("最大搜索结果数:", self.max_search_results_edit)
        
        # 搜索引擎选择
        self.search_engine_combo = _NoWheelComboBox()
        self.search_engine_combo.addItems(["DuckDuckGo", "Google", "Bing", "Baidu"])
        current_engine = self.config.get("search_engine", "Bing")
        index = self.search_engine_combo.findText(current_engine)
        if index >= 0:
            self.search_engine_combo.setCurrentIndex(index)
        general_form.addRow("搜索引擎:", self.search_engine_combo)
        
        # 连接搜索方式变化事件
        self.search_method_combo.currentTextChanged.connect(self._on_search_method_changed)
        
        # 初始化搜索引擎状态
        self._on_search_method_changed(current_method)
        
        # 浏览结果数量设置
        self.browse_count_combo = _NoWheelComboBox()
        self.browse_count_combo.addItems(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
        current_count = str(self.config.get("browse_result_count", 3))
        index = self.browse_count_combo.findText(current_count)
        if index >= 0:
            self.browse_count_combo.setCurrentIndex(index)
        else:
            self.browse_count_combo.setCurrentIndex(2)  # 默认3个
        general_form.addRow("浏览结果数量:", self.browse_count_combo)
        
        # AI智能移除设置
        self.use_ai_extraction_checkbox = QCheckBox("启用AI智能关键词提取")
        self.use_ai_extraction_checkbox.setChecked(self.config.get("use_ai_query_extraction", False))
        general_form.addRow("AI提取:", self.use_ai_extraction_checkbox)
        
        # AI提取模型选择
        self.ai_extraction_model_combo = _NoWheelComboBox()
        self.ai_extraction_model_combo.addItems([
            "gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", 
            "deepseek-chat", "deepseek-reasoner"
        ])
        current_model = self.config.get("ai_query_extraction_model", "gpt-3.5-turbo")
        index = self.ai_extraction_model_combo.findText(current_model)
        if index >= 0:
            self.ai_extraction_model_combo.setCurrentIndex(index)
        general_form.addRow("AI提取模型:", self.ai_extraction_model_combo)
        
        # 意图识别模型选择
        self.search_intent_model_combo = _NoWheelComboBox()
        self.search_intent_model_combo.addItems([
            "deepseek-chat", "deepseek-coder", "deepseek-reasoner", 
            "gpt-4-turbo", "gpt-3.5-turbo"
        ])
        current_search_model = self.config.get("search_intent_model", "deepseek-chat")
        search_index = self.search_intent_model_combo.findText(current_search_model)
        if search_index >= 0:
            self.search_intent_model_combo.setCurrentIndex(search_index)
        general_form.addRow("意图识别模型:", self.search_intent_model_combo)
        
        # 智能回忆设置
        self.max_memory_recall_combo = _NoWheelComboBox()
        self.max_memory_recall_combo.addItems(["3", "6", "9", "12", "15", "18", "21", "24"])
        current_max = str(self.config.get("max_memory_recall", 12))
        index = self.max_memory_recall_combo.findText(current_max)
        if index >= 0:
            self.max_memory_recall_combo.setCurrentIndex(index)
        general_form.addRow("智能回忆轮数:", self.max_memory_recall_combo)
        
        # 安全意图识别模型已移除
        
        # 关键词后备识别开关
        self.keyword_fallback_checkbox = QCheckBox("启用关键词后备识别")
        self.keyword_fallback_checkbox.setChecked(self.config.get("enable_keyword_fallback", True))
        self.keyword_fallback_checkbox.setToolTip("当AI意图识别失败时，使用关键词匹配作为后备方案。\n关闭此选项可以减少误识别，但可能影响某些功能的触发。")
        general_form.addRow("🔧 后备识别:", self.keyword_fallback_checkbox)
        
        model_layout.addLayout(general_form)

        model_group.setLayout(model_layout)

        # 界面设置
        ui_group = QGroupBox("界面设置")
        ui_layout = QFormLayout()

        # 消息发送快捷键（自定义输入）
        self.send_key_edit = QLineEdit()
        send_key_sequence = self.config.get("send_key_sequence", "ctrl+enter")
        self.send_key_edit.setText(send_key_sequence)
        self.send_key_edit.setPlaceholderText("例如: ctrl+enter, enter, ctrl+shift+s")
        self.send_key_edit.setToolTip("设置发送消息的快捷键\n格式: ctrl+enter, alt+s, shift+f1 等\n支持修饰键: ctrl, alt, shift, win")
        ui_layout.addRow("消息发送快捷键:", self.send_key_edit)
        
        # 窗口呼出快捷键（新增）
        self.show_window_key_edit = QLineEdit()
        show_window_key = self.config.get("show_window_key_sequence", "ctrl+shift+l")
        self.show_window_key_edit.setText(show_window_key)
        self.show_window_key_edit.setPlaceholderText("例如: ctrl+shift+l, alt+space")
        self.show_window_key_edit.setToolTip("设置窗口最小化时的呼出快捷键\n格式: ctrl+shift+l, alt+space 等\n支持修饰键: ctrl, alt, shift, win")
        ui_layout.addRow("窗口呼出快捷键:", self.show_window_key_edit)

        # 语音输入快捷键（按住说话，松开结束）
        self.voice_input_key_edit = QLineEdit()
        voice_input_key = self.config.get("voice_input_key_sequence", "")
        self.voice_input_key_edit.setText(voice_input_key)
        self.voice_input_key_edit.setPlaceholderText("留空禁用；例如: ctrl+shift+v")
        self.voice_input_key_edit.setToolTip("按下时开始录音，松开时结束并识别（等同长按麦克风按钮）\n格式: ctrl+shift+v 等\n留空则不启用该快捷键")
        ui_layout.addRow("语音输入快捷键:", self.voice_input_key_edit)

        # 窗口透明度设置
        self.transparency_slider = QSlider(Qt.Horizontal)
        self.transparency_slider.setMinimum(30)  # 最小30%透明度
        self.transparency_slider.setMaximum(100)  # 最大100%不透明
        transparency_value = self.config.get("window_transparency", 100)
        self.transparency_slider.setValue(transparency_value)
        self.transparency_slider.setTickPosition(QSlider.TicksBelow)
        self.transparency_slider.setTickInterval(10)
        
        self.transparency_label = QLabel(f"{transparency_value}%")
        self.transparency_slider.valueChanged.connect(self.on_transparency_changed)
        
        transparency_layout = QHBoxLayout()
        transparency_layout.addWidget(self.transparency_slider)
        transparency_layout.addWidget(self.transparency_label)
        ui_layout.addRow("窗口透明度:", transparency_layout)

        # 记忆系统设置
        self.show_remember_details_checkbox = QCheckBox("显示'记住这个时刻'的详细信息")
        show_remember_details = self.config.get("show_remember_details", True)
        self.show_remember_details_checkbox.setChecked(show_remember_details)
        ui_layout.addRow("记忆系统:", self.show_remember_details_checkbox)

        # AI智能创建后备机制设置
        self.ai_fallback_checkbox = QCheckBox("启用AI智能创建的后备机制（关键词识别）")
        ai_fallback_enabled = self.config.get("ai_fallback_enabled", True)
        self.ai_fallback_checkbox.setChecked(ai_fallback_enabled)
        ui_layout.addRow("AI创建:", self.ai_fallback_checkbox)

        # AI智能总结后备方案设置
        self.ai_summary_checkbox = QCheckBox("启用AI智能总结后备方案（关键词识别）")
        ai_summary_enabled = self.config.get("ai_summary_enabled", True)
        self.ai_summary_checkbox.setChecked(ai_summary_enabled)
        ui_layout.addRow("AI总结后备:", self.ai_summary_checkbox)

        # 默认保存路径设置
        default_save_path_layout = QHBoxLayout()
        self.default_save_path_edit = QLineEdit()
        self.default_save_path_edit.setText(self.config.get("default_save_path", "D:/露尼西亚文件/"))
        self.default_save_path_edit.setPlaceholderText("输入默认保存路径")
        self.browse_path_button = QPushButton("浏览...")
        self.browse_path_button.clicked.connect(self.browse_default_save_path)
        default_save_path_layout.addWidget(self.default_save_path_edit)
        default_save_path_layout.addWidget(self.browse_path_button)
        ui_layout.addRow("默认保存路径:", default_save_path_layout)

        # 笔记文件名格式设置
        self.filename_format_combo = _NoWheelComboBox()
        self.filename_format_combo.addItems(["时间戳格式 (推荐)", "简单格式"])
        filename_format = self.config.get("note_filename_format", "timestamp")
        if filename_format == "simple":
            self.filename_format_combo.setCurrentIndex(1)
        else:
            self.filename_format_combo.setCurrentIndex(0)
        ui_layout.addRow("笔记文件名格式:", self.filename_format_combo)

        ui_group.setLayout(ui_layout)

        # TTS设置
        tts_group = QGroupBox("语音合成 (TTS) 设置")
        tts_layout = QFormLayout()

        # TTS启用开关
        self.tts_enabled_checkbox = QCheckBox("启用语音合成")
        tts_enabled = self.config.get("tts_enabled", False)
        self.tts_enabled_checkbox.setChecked(tts_enabled)
        tts_layout.addRow("TTS功能:", self.tts_enabled_checkbox)

        # Azure TTS API密钥
        self.azure_tts_key_edit = QLineEdit()
        self.azure_tts_key_edit.setText(self.config.get("azure_tts_key", ""))
        tts_layout.addRow("Azure TTS API密钥:", self.create_password_input_with_toggle(
            self.azure_tts_key_edit, "输入Azure Speech Service API密钥"))

        # Azure区域
        self.azure_region_combo = _NoWheelComboBox()
        self.azure_region_combo.addItems([
            "eastasia (东亚)",
            "southeastasia (东南亚)", 
            "eastus (美国东部)",
            "westus (美国西部)",
            "northeurope (北欧)",
            "westeurope (西欧)"
        ])
        current_region = self.config.get("azure_region", "eastasia")
        region_text = f"{current_region} ({self._get_region_name(current_region)})"
        index = self.azure_region_combo.findText(region_text)
        if index >= 0:
            self.azure_region_combo.setCurrentIndex(index)
        tts_layout.addRow("Azure区域:", self.azure_region_combo)

        # TTS语音选择
        self.tts_voice_combo = _NoWheelComboBox()
        voices = [
            ("zh-CN-XiaoxiaoNeural", "晓晓 (推荐)"),
            ("zh-CN-XiaoyiNeural", "晓伊"),
            ("zh-CN-YunxiNeural", "云希"),
            ("zh-CN-YunyangNeural", "云扬"),
            ("zh-CN-XiaochenNeural", "晓辰"),
            ("zh-CN-XiaohanNeural", "晓涵"),
            ("zh-CN-XiaomoNeural", "晓墨"),
            ("zh-CN-XiaoxuanNeural", "晓萱"),
            ("zh-CN-XiaoyanNeural", "晓颜"),
            ("zh-CN-XiaoyouNeural", "晓悠"),
        ]
        for voice_id, voice_name in voices:
            self.tts_voice_combo.addItem(f"{voice_name} ({voice_id})", voice_id)
        
        current_voice = self.config.get("tts_voice", "zh-CN-XiaoxiaoNeural")
        for i in range(self.tts_voice_combo.count()):
            if self.tts_voice_combo.itemData(i) == current_voice:
                self.tts_voice_combo.setCurrentIndex(i)
                break
        tts_layout.addRow("语音选择:", self.tts_voice_combo)

        # TTS语速设置
        self.tts_speed_slider = QSlider(Qt.Horizontal)
        self.tts_speed_slider.setMinimum(50)  # 0.5倍速
        self.tts_speed_slider.setMaximum(200)  # 2.0倍速
        speed_value = int(self.config.get("tts_speaking_rate", 1.0) * 100)
        self.tts_speed_slider.setValue(speed_value)
        self.tts_speed_slider.setTickPosition(QSlider.TicksBelow)
        self.tts_speed_slider.setTickInterval(25)
        
        self.tts_speed_label = QLabel(f"{speed_value/100:.1f}x")
        self.tts_speed_slider.valueChanged.connect(
            lambda value: self.tts_speed_label.setText(f"{value/100:.1f}x")
        )
        
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(self.tts_speed_slider)
        speed_layout.addWidget(self.tts_speed_label)
        tts_layout.addRow("语速设置:", speed_layout)

        tts_group.setLayout(tts_layout)

        # Kali Linux桥接设置（HexStrike电子战工具）
        kali_group = QGroupBox("Kali Linux桥接设置（HexStrike电子战工具）")
        kali_layout = QFormLayout()

        # 启用开关
        self.kali_enabled_checkbox = QCheckBox("启用Kali Linux桥接")
        kali_config = self.config.get("kali_bridge", {})
        kali_enabled = kali_config.get("enabled", False)
        self.kali_enabled_checkbox.setChecked(kali_enabled)
        self.kali_enabled_checkbox.setToolTip("启用后，露尼西亚可以通过SSH桥接操控VMware虚拟机中的Kali Linux执行安全测试工具")
        kali_layout.addRow("启用桥接:", self.kali_enabled_checkbox)

        # SSH主机地址
        self.kali_ssh_host_edit = QLineEdit()
        self.kali_ssh_host_edit.setText(kali_config.get("ssh_host", "192.168.1.100"))
        self.kali_ssh_host_edit.setPlaceholderText("Kali Linux的IP地址")
        self.kali_ssh_host_edit.setToolTip("VMware虚拟机中Kali Linux的IP地址（桥接模式）")
        kali_layout.addRow("SSH主机:", self.kali_ssh_host_edit)

        # SSH端口
        self.kali_ssh_port_spinbox = _NoWheelSpinBox()
        self.kali_ssh_port_spinbox.setRange(1, 65535)
        self.kali_ssh_port_spinbox.setValue(kali_config.get("ssh_port", 22))
        self.kali_ssh_port_spinbox.setToolTip("SSH服务端口，默认22")
        kali_layout.addRow("SSH端口:", self.kali_ssh_port_spinbox)

        # SSH用户名
        self.kali_ssh_username_edit = QLineEdit()
        self.kali_ssh_username_edit.setText(kali_config.get("ssh_username", "kali"))
        self.kali_ssh_username_edit.setPlaceholderText("SSH用户名")
        self.kali_ssh_username_edit.setToolTip("Kali Linux的SSH登录用户名")
        kali_layout.addRow("SSH用户名:", self.kali_ssh_username_edit)

        # SSH密码（可选）
        self.kali_ssh_password_edit = QLineEdit()
        self.kali_ssh_password_edit.setText(kali_config.get("ssh_password", ""))
        self.kali_ssh_password_edit.setToolTip("SSH密码（可选，建议使用密钥认证）")
        kali_layout.addRow("SSH密码:", self.create_password_input_with_toggle(
            self.kali_ssh_password_edit, "留空则使用密钥认证"))

        # SSH密钥路径
        ssh_key_layout = QHBoxLayout()
        self.kali_ssh_key_edit = QLineEdit()
        self.kali_ssh_key_edit.setText(kali_config.get("ssh_key_path", ""))
        self.kali_ssh_key_edit.setPlaceholderText("SSH私钥路径（推荐）")
        self.kali_ssh_key_edit.setToolTip("SSH私钥文件路径，推荐使用密钥认证")
        ssh_key_layout.addWidget(self.kali_ssh_key_edit)
        
        browse_key_btn = QPushButton("浏览...")
        browse_key_btn.setMaximumWidth(80)
        browse_key_btn.clicked.connect(self.browse_ssh_key)
        ssh_key_layout.addWidget(browse_key_btn)
        kali_layout.addRow("SSH密钥:", ssh_key_layout)

        # VMware虚拟机路径（可选）
        vmware_layout = QHBoxLayout()
        self.kali_vmware_vmx_edit = QLineEdit()
        self.kali_vmware_vmx_edit.setText(kali_config.get("vmware_vmx_path", ""))
        self.kali_vmware_vmx_edit.setPlaceholderText("VMware虚拟机.vmx文件路径（可选）")
        self.kali_vmware_vmx_edit.setToolTip("用于管理虚拟机状态（启动/停止），可选")
        vmware_layout.addWidget(self.kali_vmware_vmx_edit)
        
        browse_vmware_btn = QPushButton("浏览...")
        browse_vmware_btn.setMaximumWidth(80)
        browse_vmware_btn.clicked.connect(self.browse_vmware_vmx)
        vmware_layout.addWidget(browse_vmware_btn)
        kali_layout.addRow("VMware路径:", vmware_layout)

        # 测试连接按钮
        test_connection_btn = QPushButton("测试SSH连接")
        test_connection_btn.setToolTip("测试与Kali Linux的SSH连接")
        test_connection_btn.clicked.connect(self.test_kali_connection)
        kali_layout.addRow("连接测试:", test_connection_btn)

        kali_group.setLayout(kali_layout)

        # HexStrike AI 设置（仅SSH桥接模式）
        hexstrike_group = QGroupBox("HexStrike AI 设置（150+安全工具，12+AI代理，仅SSH桥接）")
        hexstrike_layout = QFormLayout()

        # 启用开关
        self.hexstrike_enabled_checkbox = QCheckBox("启用 HexStrike AI")
        hexstrike_config = self.config.get("hexstrike_ai", {})
        hexstrike_enabled = hexstrike_config.get("enabled", False)
        self.hexstrike_enabled_checkbox.setChecked(hexstrike_enabled)
        self.hexstrike_enabled_checkbox.setToolTip("启用后，露尼西亚可以使用真实的 HexStrike AI MCP 服务器（150+工具，12+AI代理）\n仅支持SSH桥接模式，需要先配置Kali Linux桥接")
        hexstrike_layout.addRow("启用 HexStrike AI:", self.hexstrike_enabled_checkbox)

        # 服务器路径（Kali中的路径，用于自动启动）
        server_path_layout = QHBoxLayout()
        self.hexstrike_server_path_edit = QLineEdit()
        self.hexstrike_server_path_edit.setText(hexstrike_config.get("server_path", ""))
        self.hexstrike_server_path_edit.setPlaceholderText("Kali中的路径（如 /home/kali/hexstrike-ai/hexstrike_server.py）")
        self.hexstrike_server_path_edit.setToolTip("HexStrike AI 服务器脚本在Kali中的路径，如果配置了 auto_start，会自动启动服务器")
        server_path_layout.addWidget(self.hexstrike_server_path_edit)
        
        browse_server_path_btn = QPushButton("浏览...")
        browse_server_path_btn.setMaximumWidth(80)
        browse_server_path_btn.clicked.connect(self.browse_hexstrike_server_path)
        server_path_layout.addWidget(browse_server_path_btn)
        hexstrike_layout.addRow("服务器路径（Kali中）:", server_path_layout)

        # 自动启动
        self.hexstrike_auto_start_checkbox = QCheckBox("自动启动服务器")
        hexstrike_auto_start = hexstrike_config.get("auto_start", True)
        self.hexstrike_auto_start_checkbox.setChecked(hexstrike_auto_start)
        self.hexstrike_auto_start_checkbox.setToolTip("如果启用，会在需要时自动启动 HexStrike AI 服务器（需要配置服务器路径）")
        hexstrike_layout.addRow("自动启动:", self.hexstrike_auto_start_checkbox)

        # DeepSeek API配置提示
        deepseek_info_label = QLabel("💡 HexStrike AI将自动使用配置的DeepSeek API密钥和模型")
        deepseek_info_label.setStyleSheet("color: #89b4fa; font-size: 11px;")
        deepseek_info_label.setWordWrap(True)
        hexstrike_layout.addRow("", deepseek_info_label)

        # 测试连接按钮
        test_hexstrike_btn = QPushButton("测试连接")
        test_hexstrike_btn.setToolTip("测试与 HexStrike AI 服务器的SSH桥接连接")
        test_hexstrike_btn.clicked.connect(self.test_hexstrike_connection)
        hexstrike_layout.addRow("连接测试:", test_hexstrike_btn)

        hexstrike_group.setLayout(hexstrike_layout)

        # 添加所有组件到主布局
        layout.addWidget(api_group)
        layout.addWidget(browser_group)
        layout.addWidget(playwright_group)
        layout.addWidget(model_group)
        layout.addWidget(ui_group)
        layout.addWidget(tts_group)
        layout.addWidget(kali_group)
        layout.addWidget(hexstrike_group)

        # 工具管理
        tool_group = QGroupBox("工具管理")
        tool_layout = QVBoxLayout()

        # 网站管理
        website_group = QGroupBox("网站管理")
        website_layout = QVBoxLayout()

        self.website_list = QListWidget()
        for site, url in self.config.get("website_map", {}).items():
            self.website_list.addItem(f"{site}: {url}")
        website_layout.addWidget(self.website_list)

        website_btn_layout = QHBoxLayout()
        add_website_btn = QPushButton("添加网站")
        add_website_btn.clicked.connect(self.add_website)
        remove_website_btn = QPushButton("移除网站")
        remove_website_btn.clicked.connect(self.remove_website)
        website_btn_layout.addWidget(add_website_btn)
        website_btn_layout.addWidget(remove_website_btn)

        website_layout.addLayout(website_btn_layout)
        website_group.setLayout(website_layout)

        # 应用管理
        app_group = QGroupBox("应用管理")
        app_layout = QVBoxLayout()

        self.app_list = QListWidget()
        for app, path in self.config.get("app_map", {}).items():
            self.app_list.addItem(f"{app}: {path}")
        app_layout.addWidget(self.app_list)

        app_btn_layout = QHBoxLayout()
        scan_apps_btn = QPushButton("扫描应用")
        scan_apps_btn.clicked.connect(self.scan_applications)
        add_app_btn = QPushButton("添加应用")
        add_app_btn.clicked.connect(self.add_application)
        remove_app_btn = QPushButton("移除应用")
        remove_app_btn.clicked.connect(self.remove_application)
        app_btn_layout.addWidget(scan_apps_btn)
        app_btn_layout.addWidget(add_app_btn)
        app_btn_layout.addWidget(remove_app_btn)

        app_layout.addLayout(app_btn_layout)
        app_group.setLayout(app_layout)

        tool_layout.addWidget(website_group)
        tool_layout.addWidget(app_group)
        tool_group.setLayout(tool_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addWidget(tool_group)
        
        # 将滚动内容设置到滚动区域
        scroll_area.setWidget(scroll_content)
        
        # 创建按钮布局（不在滚动区域内）
        main_layout.addWidget(scroll_area)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)
    
    def on_transparency_changed(self, value):
        """透明度滑块值改变时的处理"""
        # 更新标签显示
        self.transparency_label.setText(f"{value}%")
        
        # 如果有回调函数，实时更新主窗口透明度
        if self.transparency_callback:
            try:
                self.transparency_callback(value)
            except Exception as e:
                print(f"⚠️ 实时更新透明度失败: {str(e)}")
    
    def add_website(self):
        """添加网站"""
        site, ok1 = QInputDialog.getText(self, "添加网站", "输入网站名称:")
        if not ok1 or not site:
            return

        url, ok2 = QInputDialog.getText(self, "添加网站", "输入网站URL:")
        if ok2 and url:
            self.website_list.addItem(f"{site}: {url}")

    def remove_website(self):
        """移除网站"""
        if self.website_list.currentRow() >= 0:
            self.website_list.takeItem(self.website_list.currentRow())

    def scan_applications(self):
        """扫描应用程序"""
        apps = scan_windows_apps()
        self.app_list.clear()
        for app_name, app_path in apps.items():
            self.app_list.addItem(f"{app_name}: {app_path}")

    def add_application(self):
        """添加应用程序"""
        app_name, ok1 = QInputDialog.getText(self, "添加应用", "输入应用名称:")
        if not ok1 or not app_name:
            return

        app_path, ok2 = QFileDialog.getOpenFileName(self, "选择应用程序", "",
                                                    "Executable Files (*.exe;*.lnk);;All Files (*)")
        if ok2 and app_path:
            self.app_list.addItem(f"{app_name}: {app_path}")

    def remove_application(self):
        """移除应用程序"""
        if self.app_list.currentRow() >= 0:
            self.app_list.takeItem(self.app_list.currentRow())

    def browse_default_save_path(self):
        """浏览默认保存路径"""
        current_path = self.default_save_path_edit.text().strip()
        if not current_path:
            current_path = "D:/"
        
        # 确保路径存在，如果不存在则创建
        if not os.path.exists(current_path):
            try:
                os.makedirs(current_path, exist_ok=True)
            except:
                current_path = "D:/"
        
        folder_path = QFileDialog.getExistingDirectory(
            self, 
            "选择默认保存路径", 
            current_path,
            QFileDialog.ShowDirsOnly
        )
        
        if folder_path:
            # 确保路径以斜杠结尾
            if not folder_path.endswith('/') and not folder_path.endswith('\\'):
                folder_path += '/'
            self.default_save_path_edit.setText(folder_path)
    
    def on_llm_type_changed(self, llm_type):
        """当LLM类型改变时（本地/云端），显示/隐藏相关配置"""
        is_local = (llm_type == "本地模型")
        is_cloud = (llm_type == "云端API")
        
        # 显示/隐藏云端提供商选择
        if hasattr(self, 'cloud_provider_combo'):
            self.cloud_provider_combo.setVisible(is_cloud)
        if hasattr(self, 'cloud_provider_combo_label'):
            self.cloud_provider_combo_label.setVisible(is_cloud)
        
        # 显示/隐藏Ollama配置区域
        if hasattr(self, 'ollama_label'):
            self.ollama_label.setVisible(is_local)
        if hasattr(self, 'ollama_url_edit'):
            self.ollama_url_edit.setVisible(is_local)
        if hasattr(self, 'ollama_model_combo'):
            self.ollama_model_combo.setVisible(is_local)
        if hasattr(self, 'refresh_ollama_btn'):
            self.refresh_ollama_btn.setVisible(is_local)
        if hasattr(self, 'ollama_form'):
            # 显示/隐藏整个表单的所有widget
            for i in range(self.ollama_form.count()):
                item = self.ollama_form.itemAt(i)
                if item and item.widget():
                    item.widget().setVisible(is_local)
        
        # 显示/隐藏云端API配置区域
        if hasattr(self, 'cloud_label'):
            self.cloud_label.setVisible(is_cloud)
        if hasattr(self, 'chat_model_combo'):
            self.chat_model_combo.setVisible(is_cloud)
        if hasattr(self, 'memory_model_combo'):
            self.memory_model_combo.setVisible(is_cloud)
        if hasattr(self, 'cloud_form'):
            # 显示/隐藏整个表单的所有widget
            for i in range(self.cloud_form.count()):
                item = self.cloud_form.itemAt(i)
                if item and item.widget():
                    item.widget().setVisible(is_cloud)
    
    def on_cloud_provider_changed(self, provider):
        """当云端提供商改变时的回调（预留用于将来扩展）"""
        pass
    
    def refresh_ollama_models(self):
        """刷新本地Ollama模型列表"""
        import requests
        import json
        
        if not hasattr(self, 'ollama_model_combo'):
            return
        
        # 保存当前选中的模型
        current_model = self.config.get("ollama_model", "qwen2.5:latest")
        
        # 清空下拉框
        self.ollama_model_combo.clear()
        
        try:
            # 获取Ollama服务器地址
            ollama_url = self.ollama_url_edit.text().strip() if hasattr(self, 'ollama_url_edit') else "http://localhost:11434"
            if not ollama_url:
                ollama_url = "http://localhost:11434"
            
            # 调用Ollama API获取模型列表
            response = requests.get(f"{ollama_url}/api/tags", timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                
                if models:
                    # 添加扫描到的模型
                    model_names = []
                    for model in models:
                        name = model.get("name", "")
                        if name:
                            model_names.append(name)
                            # 显示模型名称和大小
                            size_gb = model.get("size", 0) / (1024**3)
                            display_name = f"{name} ({size_gb:.1f}GB)"
                            self.ollama_model_combo.addItem(display_name, name)
                    
                    # 设置当前选中的模型
                    found = False
                    for i in range(self.ollama_model_combo.count()):
                        if self.ollama_model_combo.itemData(i) == current_model:
                            self.ollama_model_combo.setCurrentIndex(i)
                            found = True
                            break
                    
                    if not found and model_names:
                        # 如果没找到配置中的模型，尝试匹配模型名（不含tag）
                        current_base = current_model.split(':')[0] if ':' in current_model else current_model
                        for i in range(self.ollama_model_combo.count()):
                            model_name = self.ollama_model_combo.itemData(i)
                            base_name = model_name.split(':')[0] if ':' in model_name else model_name
                            if base_name == current_base:
                                self.ollama_model_combo.setCurrentIndex(i)
                                found = True
                                break
                    
                    if not found:
                        # 如果还是没找到，手动添加配置中的模型
                        self.ollama_model_combo.addItem(f"{current_model} (已配置)", current_model)
                        self.ollama_model_combo.setCurrentIndex(self.ollama_model_combo.count() - 1)
                    
                    print(f"✅ 成功扫描到 {len(model_names)} 个Ollama模型")
                else:
                    # 没有模型，添加默认选项
                    self.ollama_model_combo.addItem("未检测到模型", "")
                    self.ollama_model_combo.addItem(f"{current_model} (手动输入)", current_model)
                    self.ollama_model_combo.setCurrentIndex(1)
                    print("⚠️ Ollama服务运行中，但未检测到已安装的模型")
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            # 超时，添加手动输入选项
            self.ollama_model_combo.addItem("⚠️ 连接超时", "")
            self.ollama_model_combo.addItem(f"{current_model} (手动输入)", current_model)
            self.ollama_model_combo.setCurrentIndex(1)
            print(f"⚠️ 无法连接到Ollama服务 ({ollama_url})：连接超时")
            
        except requests.exceptions.ConnectionError:
            # 连接失败，添加手动输入选项
            self.ollama_model_combo.addItem("⚠️ 未启动Ollama服务", "")
            self.ollama_model_combo.addItem(f"{current_model} (手动输入)", current_model)
            self.ollama_model_combo.setCurrentIndex(1)
            print(f"⚠️ 无法连接到Ollama服务 ({ollama_url})：请确保Ollama已启动")
            
        except Exception as e:
            # 其他错误，添加手动输入选项
            self.ollama_model_combo.addItem(f"⚠️ 扫描失败: {str(e)[:30]}", "")
            self.ollama_model_combo.addItem(f"{current_model} (手动输入)", current_model)
            self.ollama_model_combo.setCurrentIndex(1)
            print(f"⚠️ 扫描Ollama模型时出错: {e}")
    
    def test_cdp_connection(self):
        """测试CDP连接"""
        import requests
        
        cdp_url = self.playwright_cdp_url_input.text().strip()
        if not cdp_url:
            cdp_url = "http://localhost:9222"
        
        # 确保URL格式正确
        if not cdp_url.startswith("http"):
            cdp_url = "http://" + cdp_url
        
        test_url = f"{cdp_url}/json"
        
        # 创建进度对话框
        progress = QProgressDialog("正在测试连接...", "取消", 0, 0, self)
        progress.setWindowTitle("CDP连接测试")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        try:
            response = requests.get(test_url, timeout=3)
            progress.close()
            
            if response.status_code == 200:
                data = response.json()
                tab_count = len(data)
                
                # 构建详细信息
                details = f"连接成功！\n\n"
                details += f"调试地址: {cdp_url}\n"
                details += f"检测到 {tab_count} 个浏览器标签页\n\n"
                
                if tab_count > 0:
                    details += "标签页列表:\n"
                    for i, tab in enumerate(data[:5], 1):  # 只显示前5个
                        title = tab.get('title', '(无标题)')[:50]
                        details += f"{i}. {title}\n"
                    
                    if tab_count > 5:
                        details += f"... 还有 {tab_count - 5} 个标签页"
                
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("✅ 连接成功")
                msg_box.setText("CDP调试端口连接成功！")
                msg_box.setDetailedText(details)
                msg_box.setIcon(QMessageBox.Information)
                msg_box.exec_()
            else:
                QMessageBox.warning(
                    self,
                    "❌ 连接失败",
                    f"HTTP 错误: {response.status_code}\n\n"
                    f"请检查:\n"
                    f"1. CDP地址是否正确\n"
                    f"2. 浏览器是否正在运行"
                )
        
        except requests.exceptions.ConnectionError:
            progress.close()
            QMessageBox.warning(
                self,
                "❌ 连接失败",
                f"无法连接到 {cdp_url}\n\n"
                f"可能的原因:\n"
                f"1. 浏览器未启动调试模式\n"
                f"2. 调试端口不是 9222\n"
                f"3. 防火墙拦截\n\n"
                f"解决方法:\n"
                f"• 运行 start_edge_debug.bat\n"
                f"• 或手动启动:\n"
                f'  "msedge.exe" --remote-debugging-port=9222'
            )
        
        except requests.exceptions.Timeout:
            progress.close()
            QMessageBox.warning(
                self,
                "⏱️ 连接超时",
                f"连接超时（3秒）\n\n"
                f"请检查:\n"
                f"1. CDP地址是否正确\n"
                f"2. 网络是否正常"
            )
        
        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self,
                "❌ 测试失败",
                f"发生错误: {str(e)}\n\n"
                f"请检查CDP地址格式是否正确"
            )

    def save_settings(self):
        """保存设置"""
        # 保存API密钥
        self.config["openai_key"] = self.openai_key_edit.text()
        self.config["deepseek_key"] = self.deepseek_key_edit.text()
        self.config["qwen3vl_plus_key"] = self.qwen3vl_plus_key_edit.text()
        self.config["dashscope_key"] = self.dashscope_key_edit.text()
        self.config["voice_auto_send"] = self.voice_auto_send_checkbox.isChecked()
        self.config["heweather_key"] = self.weather_key_edit.text()
        self.config["amap_key"] = self.amap_key_edit.text()

        # 保存天气数据来源设置
        self.config["weather_source"] = self.weather_source_combo.currentText()

        # 保存浏览器设置
        browser_text = self.default_browser_combo.currentText()
        if browser_text == "默认浏览器":
            self.config["default_browser"] = ""
        else:
            self.config["default_browser"] = browser_text
        self.config["default_search_engine"] = self.default_search_engine_combo.currentText()
        
        # 保存界面设置
        # 保存消息发送快捷键
        if hasattr(self, 'send_key_edit') and self.send_key_edit:
            send_key_sequence = self.send_key_edit.text().strip().lower()
            if send_key_sequence:
                self.config["send_key_sequence"] = send_key_sequence
            else:
                self.config["send_key_sequence"] = "ctrl+enter"
            # 为了向后兼容，也保存旧的格式
            if send_key_sequence in ["enter", "return"]:
                self.config["send_key_mode"] = "Enter"
            else:
                self.config["send_key_mode"] = "Ctrl+Enter"
        
        # 保存窗口呼出快捷键
        if hasattr(self, 'show_window_key_edit') and self.show_window_key_edit:
            show_window_key_sequence = self.show_window_key_edit.text().strip().lower()
            if show_window_key_sequence:
                self.config["show_window_key_sequence"] = show_window_key_sequence
            else:
                self.config["show_window_key_sequence"] = "ctrl+shift+l"

        # 保存语音输入快捷键
        if hasattr(self, 'voice_input_key_edit') and self.voice_input_key_edit:
            self.config["voice_input_key_sequence"] = self.voice_input_key_edit.text().strip().lower()
        
        # 保存 Playwright 配置
        self.config["playwright_mode"] = self.playwright_mode_combo.currentText()
        self.config["playwright_slow_mo"] = self.playwright_slow_mo_spinbox.value()
        self.config["playwright_cdp_url"] = self.playwright_cdp_url_input.text().strip()
        self.config["playwright_user_data_dir"] = self.playwright_user_data_dir_input.text().strip()
        
        # 保存联网搜索设置
        checkbox_state = self.enable_web_search_checkbox.isChecked()
        self.config["enable_web_search"] = checkbox_state
        print(f"🔍 [设置保存] 复选框状态: {checkbox_state}")
        print(f"🔍 [设置保存] 保存到config: enable_web_search = {self.config['enable_web_search']}")
        
        # 保存搜索方式和搜索引擎选择
        self.config["search_method"] = self.search_method_combo.currentText()
        self.config["search_engine"] = self.search_engine_combo.currentText()
        
        # 保存搜索问题数量和结果数量
        try:
            max_search_questions = int(self.max_search_questions_edit.text())
            if 1 <= max_search_questions <= 6:
                self.config["max_search_questions"] = max_search_questions
            else:
                QMessageBox.warning(self, "警告", "最大搜索问题数必须在1到6之间！")
                return
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的最大搜索问题数！")
            return
        
        try:
            max_search_results = int(self.max_search_results_edit.text())
            if max_search_results > 0:
                self.config["max_search_results"] = max_search_results
            else:
                QMessageBox.warning(self, "警告", "最大搜索结果数必须大于0！")
                return
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的最大搜索结果数！")
            return
        
        # 保存浏览结果数量设置
        self.config["browse_result_count"] = int(self.browse_count_combo.currentText())
        
        # 保存AI智能移除设置
        self.config["use_ai_query_extraction"] = self.use_ai_extraction_checkbox.isChecked()
        self.config["ai_query_extraction_model"] = self.ai_extraction_model_combo.currentText()
        
        # 保存搜索意图识别模型设置
        self.config["search_intent_model"] = self.search_intent_model_combo.currentText()
        
        # 保存智能回忆设置
        self.config["max_memory_recall"] = int(self.max_memory_recall_combo.currentText())
        
        # 安全意图识别模型已移除
        
        # 保存关键词后备识别设置
        self.config["enable_keyword_fallback"] = self.keyword_fallback_checkbox.isChecked()

        # 保存LLM提供商和Ollama配置
        llm_type = self.llm_type_combo.currentText()
        if llm_type == "本地模型":
            self.config["llm_provider"] = "Ollama"
        else:  # 云端API
            self.config["llm_provider"] = self.cloud_provider_combo.currentText()  # DeepSeek 或 OpenAI
        
        self.config["ollama_url"] = self.ollama_url_edit.text().strip()
        
        # 从下拉框获取实际的模型名称（使用itemData存储的真实名称）
        current_index = self.ollama_model_combo.currentIndex()
        if current_index >= 0:
            model_name = self.ollama_model_combo.itemData(current_index)
            if model_name:  # 如果有存储的真实名称，使用它
                self.config["ollama_model"] = model_name
            else:  # 否则使用显示的文本（手动输入的情况）
                self.config["ollama_model"] = self.ollama_model_combo.currentText().strip()
        else:
            self.config["ollama_model"] = self.ollama_model_combo.currentText().strip()

        # 保存模型选择
        self.config["selected_model"] = self.chat_model_combo.currentText()
        
        # 保存识底深湖模型选择
        self.config["memory_summary_model"] = self.memory_model_combo.currentText()

        # 保存AI Token数设置
        try:
            max_tokens = int(self.max_tokens_edit.text())
            if max_tokens < 0:
                max_tokens = 0  # 0表示无限制
            self.config["max_tokens"] = max_tokens
        except ValueError:
            self.config["max_tokens"] = 1000  # 默认值

        # 保存窗口透明度设置
        self.config["window_transparency"] = self.transparency_slider.value()

        # 保存记忆系统设置
        self.config["show_remember_details"] = self.show_remember_details_checkbox.isChecked()

        # 保存AI智能创建后备机制设置
        self.config["ai_fallback_enabled"] = self.ai_fallback_checkbox.isChecked()

        # 保存AI智能总结设置
        self.config["ai_summary_enabled"] = self.ai_summary_checkbox.isChecked()

        # 保存默认保存路径设置
        self.config["default_save_path"] = self.default_save_path_edit.text().strip()

        # 保存笔记文件名格式设置
        filename_format_index = self.filename_format_combo.currentIndex()
        if filename_format_index == 1:  # 简单格式
            self.config["note_filename_format"] = "simple"
        else:  # 时间戳格式
            self.config["note_filename_format"] = "timestamp"

        # 保存TTS设置
        self.config["tts_enabled"] = self.tts_enabled_checkbox.isChecked()
        self.config["azure_tts_key"] = self.azure_tts_key_edit.text()
        
        # 保存Azure区域
        region_text = self.azure_region_combo.currentText()
        self.config["azure_region"] = self._get_region_code(region_text)
        
        # 保存TTS语音
        voice_index = self.tts_voice_combo.currentIndex()
        if voice_index >= 0:
            self.config["tts_voice"] = self.tts_voice_combo.itemData(voice_index)
        
        # 保存TTS语速
        speed_value = self.tts_speed_slider.value() / 100.0
        self.config["tts_speaking_rate"] = speed_value

        # 保存Kali Linux桥接设置
        kali_bridge_config = {
            "enabled": self.kali_enabled_checkbox.isChecked(),
            "ssh_host": self.kali_ssh_host_edit.text().strip(),
            "ssh_port": self.kali_ssh_port_spinbox.value(),
            "ssh_username": self.kali_ssh_username_edit.text().strip(),
            "ssh_password": self.kali_ssh_password_edit.text().strip(),
            "ssh_key_path": self.kali_ssh_key_edit.text().strip(),
            "vmware_vmx_path": self.kali_vmware_vmx_edit.text().strip()
        }
        self.config["kali_bridge"] = kali_bridge_config

        # 保存 HexStrike AI 设置（仅SSH桥接模式）
        hexstrike_ai_config = {
            "enabled": self.hexstrike_enabled_checkbox.isChecked(),
            "connection_mode": "ssh",  # 固定为SSH桥接模式
            "server_url": "http://localhost:8888",  # SSH桥接模式下固定
            "server_path": self.hexstrike_server_path_edit.text().strip(),
            "auto_start": self.hexstrike_auto_start_checkbox.isChecked(),
            "use_for_complex_tasks": True
        }
        self.config["hexstrike_ai"] = hexstrike_ai_config

        # 保存网站映射
        website_map = {}
        for i in range(self.website_list.count()):
            item_text = self.website_list.item(i).text()
            if ": " in item_text:
                site, url = item_text.split(": ", 1)
                website_map[site] = url
        self.config["website_map"] = website_map

        # 保存应用映射
        app_map = {}
        for i in range(self.app_list.count()):
            item_text = self.app_list.item(i).text()
            if ": " in item_text:
                app, path = item_text.split(": ", 1)
                app_map[app] = path
        self.config["app_map"] = app_map

        # 保存到文件
        save_config(self.config)
        print(f"✅ [配置已保存到文件] enable_web_search: {self.config.get('enable_web_search')}")
        self.accept()
    
    def _get_region_name(self, region_code: str) -> str:
        """获取区域名称"""
        region_names = {
            "eastasia": "东亚",
            "southeastasia": "东南亚",
            "eastus": "美国东部",
            "westus": "美国西部",
            "northeurope": "北欧",
            "westeurope": "西欧"
        }
        return region_names.get(region_code, region_code)
    
    def _get_region_code(self, region_text: str) -> str:
        """从区域文本中提取区域代码"""
        return region_text.split(" ")[0]
    
    def _on_search_method_changed(self, method):
        """搜索方式变化时的处理"""
        if method == "DuckDuckGo":
            # DuckDuckGo模式下，只能选择DuckDuckGo
            self.search_engine_combo.setEnabled(False)
            self.search_engine_combo.setCurrentText("DuckDuckGo")
        elif method == "Playwright":
            # Playwright模式下，可以选择Google、Bing、Baidu
            self.search_engine_combo.setEnabled(True)
            # 如果当前是DuckDuckGo，切换为Bing（推荐）
            if self.search_engine_combo.currentText() == "DuckDuckGo":
                self.search_engine_combo.setCurrentText("Bing")
    
    def browse_ssh_key(self):
        """浏览SSH密钥文件"""
        current_path = self.kali_ssh_key_edit.text().strip()
        if not current_path:
            current_path = os.path.expanduser("~/.ssh")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择SSH私钥文件",
            current_path,
            "All Files (*);;Private Key (*.pem *.key);;RSA Key (*.rsa)"
        )
        
        if file_path:
            self.kali_ssh_key_edit.setText(file_path)
    
    def browse_vmware_vmx(self):
        """浏览VMware虚拟机.vmx文件"""
        current_path = self.kali_vmware_vmx_edit.text().strip()
        if not current_path:
            current_path = os.path.expanduser("~/Documents/Virtual Machines")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择VMware虚拟机.vmx文件",
            current_path,
            "VMware Virtual Machine (*.vmx);;All Files (*)"
        )
        
        if file_path:
            self.kali_vmware_vmx_edit.setText(file_path)
    
    
    def browse_hexstrike_server_path(self):
        """浏览HexStrike AI服务器脚本路径（Kali中的路径，手动输入）"""
        QMessageBox.information(
            self,
            "提示",
            "SSH桥接模式下，服务器路径是Kali Linux中的路径。\n\n"
            "请手动输入路径，例如：\n"
            "/home/kali/hexstrike-ai/hexstrike_server.py\n\n"
            "或使用相对路径（从HexStrike AI安装目录）：\n"
            "hexstrike_server.py"
        )
    
    def test_hexstrike_connection(self):
        """测试HexStrike AI服务器连接（仅SSH桥接模式）"""
        self._test_hexstrike_connection_ssh()
    
    def _test_hexstrike_connection_ssh(self):
        """SSH桥接模式测试连接"""
        # 检查Kali桥接是否配置
        kali_config = self.config.get("kali_bridge", {})
        if not kali_config.get("enabled", False):
            QMessageBox.warning(
                self,
                "警告",
                "SSH桥接模式需要先启用Kali桥接。\n\n"
                "请在\"Kali Linux桥接设置\"中：\n"
                "1. 启用Kali Linux桥接\n"
                "2. 配置SSH连接信息"
            )
            return
        
        # 创建进度对话框
        progress = QProgressDialog("正在测试SSH桥接连接...", "取消", 0, 0, self)
        progress.setWindowTitle("HexStrike AI SSH桥接测试")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        try:
            from vmware_kali_bridge import VMwareKaliBridge
            
            # 创建Kali桥接
            kali_bridge = VMwareKaliBridge(kali_config)
            progress.setLabelText("正在检查HexStrike AI服务器...")
            
            # 检查服务器是否在Kali中运行
            check_cmd = "curl -s http://localhost:8888/health 2>/dev/null || echo 'not_running'"
            result = kali_bridge.execute_command(check_cmd, timeout=10)
            
            progress.close()
            
            if result.get("success") and "not_running" not in result.get("stdout", ""):
                # 尝试获取工具列表
                try:
                    import json
                    tools_count = 0
                    
                    # 方法1：尝试从 /api/tools/list 获取
                    tools_cmd = "curl -s http://localhost:8888/api/tools/list"
                    tools_result = kali_bridge.execute_command(tools_cmd, timeout=10)
                    
                    if tools_result.get("success"):
                        stdout = tools_result.get("stdout", "")
                        # 检查是否是404错误
                        if "<!doctype html>" not in stdout.lower() and "404" not in stdout and "Not Found" not in stdout:
                            try:
                                tools_data = json.loads(stdout)
                                tools_list = tools_data.get("tools", [])
                                if tools_list:
                                    tools_count = len(tools_list)
                            except json.JSONDecodeError:
                                pass
                    
                    # 方法2：如果方法1失败，从 /health 端点提取
                    if tools_count == 0:
                        health_cmd = "curl -s http://localhost:8888/health"
                        health_result = kali_bridge.execute_command(health_cmd, timeout=10)
                        
                        if health_result.get("success"):
                            try:
                                health_data = json.loads(health_result.get("stdout", "{}"))
                                tools_status = health_data.get("tools_status", {})
                                # 提取所有可用的工具（值为True的工具）
                                tools_count = sum(1 for available in tools_status.values() if available)
                            except json.JSONDecodeError:
                                pass
                    
                    if tools_count > 0:
                        QMessageBox.information(
                            self,
                            "连接成功",
                            f"✅ HexStrike AI 服务器连接成功（SSH桥接）！\n\n"
                            f"连接方式: SSH桥接到Kali Linux\n"
                            f"Kali主机: {kali_config.get('ssh_host', 'N/A')}\n"
                            f"可用工具数量: {tools_count}\n\n"
                            f"现在可以使用所有 HexStrike AI 工具了。"
                        )
                    else:
                        QMessageBox.warning(
                            self,
                            "连接成功但无法获取工具列表",
                            f"✅ 服务器连接成功，但无法获取工具列表。\n\n"
                            f"请检查服务器是否正常运行，或查看HexStrike AI的API文档。"
                        )
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "连接成功但无法获取工具列表",
                        f"✅ 服务器连接成功，但获取工具列表时出错：\n{str(e)}"
                    )
            else:
                server_path = self.hexstrike_server_path_edit.text().strip()
                if server_path:
                    QMessageBox.warning(
                        self,
                        "服务器未运行",
                        f"❌ HexStrike AI 服务器在Kali中未运行。\n\n"
                        f"服务器路径: {server_path}\n\n"
                        f"请确保：\n"
                        f"1. HexStrike AI已安装在Kali中\n"
                        f"2. 服务器路径正确\n"
                        f"3. 启用自动启动或手动启动服务器"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "配置不完整",
                        f"❌ 请配置Kali中的服务器路径。\n\n"
                        f"例如：/home/kali/hexstrike-ai/hexstrike_server.py"
                    )
        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self,
                "错误",
                f"❌ 测试SSH桥接连接时发生错误：\n{str(e)}"
            )
    
    def test_kali_connection(self):
        """测试Kali Linux SSH连接"""
        ssh_host = self.kali_ssh_host_edit.text().strip()
        ssh_port = self.kali_ssh_port_spinbox.value()
        ssh_username = self.kali_ssh_username_edit.text().strip()
        ssh_password = self.kali_ssh_password_edit.text().strip()
        ssh_key_path = self.kali_ssh_key_edit.text().strip()
        
        if not ssh_host:
            QMessageBox.warning(self, "警告", "请输入SSH主机地址")
            return
        
        if not ssh_username:
            QMessageBox.warning(self, "警告", "请输入SSH用户名")
            return
        
        if not ssh_password and not ssh_key_path:
            QMessageBox.warning(self, "警告", "请配置SSH密码或密钥路径")
            return
        
        # 创建进度对话框
        progress = QProgressDialog("正在测试SSH连接...", "取消", 0, 0, self)
        progress.setWindowTitle("SSH连接测试")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        try:
            import paramiko
            
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 尝试连接
            if ssh_key_path and os.path.exists(ssh_key_path):
                ssh_client.connect(
                    hostname=ssh_host,
                    port=ssh_port,
                    username=ssh_username,
                    key_filename=ssh_key_path,
                    timeout=10
                )
            elif ssh_password:
                ssh_client.connect(
                    hostname=ssh_host,
                    port=ssh_port,
                    username=ssh_username,
                    password=ssh_password,
                    timeout=10
                )
            else:
                progress.close()
                QMessageBox.warning(self, "错误", "未配置SSH认证方式")
                return
            
            # 测试执行命令
            stdin, stdout, stderr = ssh_client.exec_command("whoami", timeout=5)
            result = stdout.read().decode('utf-8', errors='ignore').strip()
            return_code = stdout.channel.recv_exit_status()
            
            ssh_client.close()
            progress.close()
            
            if return_code == 0:
                # 检查可用工具
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                if ssh_key_path and os.path.exists(ssh_key_path):
                    ssh_client.connect(
                        hostname=ssh_host,
                        port=ssh_port,
                        username=ssh_username,
                        key_filename=ssh_key_path,
                        timeout=10
                    )
                else:
                    ssh_client.connect(
                        hostname=ssh_host,
                        port=ssh_port,
                        username=ssh_username,
                        password=ssh_password,
                        timeout=10
                    )
                
                # 检查常用工具
                tools = ["nmap", "gobuster", "nikto", "sqlmap", "subfinder", "nuclei"]
                available_tools = []
                for tool in tools:
                    stdin, stdout, stderr = ssh_client.exec_command(f"which {tool}", timeout=5)
                    if stdout.channel.recv_exit_status() == 0:
                        available_tools.append(tool)
                
                ssh_client.close()
                
                details = f"✅ SSH连接成功！\n\n"
                details += f"主机: {ssh_host}:{ssh_port}\n"
                details += f"用户: {result}\n\n"
                details += f"可用工具: {', '.join(available_tools) if available_tools else '未检测到常用工具'}\n"
                details += f"检测到的工具数量: {len(available_tools)}/{len(tools)}"
                
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("✅ 连接成功")
                msg_box.setText("SSH连接测试成功！")
                msg_box.setDetailedText(details)
                msg_box.setIcon(QMessageBox.Information)
                msg_box.exec_()
            else:
                QMessageBox.warning(
                    self,
                    "❌ 连接失败",
                    f"SSH连接成功，但命令执行失败\n\n返回码: {return_code}\n错误: {stderr.read().decode('utf-8', errors='ignore')}"
                )
        
        except paramiko.AuthenticationException:
            progress.close()
            QMessageBox.warning(
                self,
                "❌ 认证失败",
                "SSH认证失败\n\n请检查:\n"
                "1. 用户名是否正确\n"
                "2. 密码是否正确\n"
                "3. 密钥文件是否正确"
            )
        except paramiko.SSHException as e:
            progress.close()
            QMessageBox.warning(
                self,
                "❌ SSH错误",
                f"SSH连接错误: {str(e)}\n\n请检查:\n"
                "1. SSH服务是否运行\n"
                "2. 端口是否正确\n"
                "3. 防火墙设置"
            )
        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self,
                "❌ 连接失败",
                f"无法连接到Kali Linux\n\n错误: {str(e)}\n\n请检查:\n"
                "1. Kali Linux是否运行\n"
                "2. 网络连接是否正常\n"
                "3. IP地址是否正确\n"
                "4. 是否配置了桥接网络"
            )


class MemoryLakeDialog(QDialog):
    """识底深湖记忆系统对话框"""
    
    def __init__(self, memory_lake, parent=None):
        super().__init__(parent)
        self.memory_lake = memory_lake
        self.setWindowTitle("识底深湖 - 记忆系统")
        self.setGeometry(200, 200, 800, 700)  # 增加窗口高度
        
        # 设置图标
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))
        
        self.init_ui()
        self.refresh_data()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 统计信息区域
        stats_group = QGroupBox("记忆统计")
        stats_group.setStyleSheet("""
            QGroupBox {
                color: #cdd6f4;
                font-size: 14px;
                border: 1px solid #45475a;
                border-radius: 5px;
                margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #1e1e2e;
            }
        """)
        stats_layout = QHBoxLayout()
        
        self.stats_label = QLabel("加载中...")
        self.stats_label.setStyleSheet("color: #a6e3a1; font-size: 12px;")
        stats_layout.addWidget(self.stats_label)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        stats_layout.addWidget(refresh_btn)
        
        stats_group.setLayout(stats_layout)
        
        # 主题索引区域
        topics_group = QGroupBox("主题索引")
        topics_group.setStyleSheet("""
            QGroupBox {
                color: #cdd6f4;
                font-size: 14px;
                border: 1px solid #45475a;
                border-radius: 5px;
                margin-top: 2ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #1e1e2e;
            }
        """)
        topics_layout = QVBoxLayout()
        
        # 搜索框
        search_layout = QHBoxLayout()
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索主题...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 12px;
            }
        """)
        self.search_edit.textChanged.connect(self.filter_topics)
        search_layout.addWidget(self.search_edit)
        
        topics_layout.addLayout(search_layout)
        
        # 添加一些间距，避免标题被遮挡
        topics_layout.addSpacing(10)
        
        # 主题列表
        self.topics_list = QListWidget()
        self.topics_list.setStyleSheet("""
            QListWidget {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #45475a;
            }
            QListWidget::item:selected {
                background-color: #89b4fa;
                color: #1e1e1e;
            }
        """)
        self.topics_list.itemClicked.connect(self.show_topic_details)
        topics_layout.addWidget(self.topics_list)
        
        topics_group.setLayout(topics_layout)
        
        # 详情区域
        details_group = QGroupBox("主题详情")
        details_group.setStyleSheet("""
            QGroupBox {
                color: #cdd6f4;
                font-size: 14px;
                border: 1px solid #45475a;
                border-radius: 5px;
                margin-top: 2ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #1e1e2e;
            }
        """)
        details_layout = QVBoxLayout()
        
        # 重点记忆标签区域
        important_layout = QHBoxLayout()
        
        self.important_label = QLabel("⭐ 重点记忆")
        self.important_label.setStyleSheet("""
            QLabel {
                color: #f9e2af;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 10px;
                background-color: #313244;
                border-radius: 5px;
                border: 1px solid #f9e2af;
            }
        """)
        self.important_label.setVisible(False)
        
        self.important_btn = QPushButton("标记为重点记忆")
        self.important_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9e2af;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #fab387;
            }
        """)
        self.important_btn.clicked.connect(self.toggle_important_memory)
        self.important_btn.setVisible(False)
        
        important_layout.addStretch()
        important_layout.addWidget(self.important_label)
        important_layout.addWidget(self.important_btn)
        
        details_layout.addLayout(important_layout)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 10px;
                font-size: 12px;
            }
        """)
        details_layout.addWidget(self.details_text)
        
        # 添加一些间距，避免标题被遮挡
        details_layout.addSpacing(10)
        
        details_group.setLayout(details_layout)
        
        # 添加到主布局
        layout.addWidget(stats_group)
        layout.addWidget(topics_group, 2)
        layout.addWidget(details_group, 1)
        
        self.setLayout(layout)
    
    def refresh_data(self):
        """刷新记忆数据"""
        stats = self.memory_lake.get_memory_stats()
        self.stats_label.setText(
            f"总主题数: {stats['total_topics']} | "
            f"重点记忆: {stats['important_topics']} | "
            f"日志文件数: {stats['total_log_files']} | "
            f"记忆文件大小: {stats['memory_file_size']} bytes"
        )
        
        self.load_topics()
    
    def load_topics(self):
        """加载主题列表"""
        self.topics_list.clear()
        try:
            topics = self.memory_lake.memory_index.get("topics", [])
            
            for topic in reversed(topics):  # 最新的在前面
                if isinstance(topic, dict) and 'date' in topic and 'timestamp' in topic and 'topic' in topic:
                    # 添加重点记忆标识
                    important_icon = "⭐ " if topic.get("is_important", False) else ""
                    item_text = f"{important_icon}[{topic['date']} {topic['timestamp']}] {topic['topic']}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, topic)
                    self.topics_list.addItem(item)
        except Exception as e:
            print(f"加载主题列表失败: {str(e)}")
    
    def filter_topics(self):
        """过滤主题"""
        search_text = self.search_edit.text().lower()
        for i in range(self.topics_list.count()):
            item = self.topics_list.item(i)
            item.setHidden(search_text not in item.text().lower())
    
    def show_topic_details(self, item):
        """显示主题详情"""
        topic_data = item.data(Qt.UserRole)
        if not topic_data:
            return
        
        # 显示重点记忆标签
        is_important = topic_data.get("is_important", False)
        self.important_label.setVisible(is_important)
        self.important_btn.setVisible(True)
        
        if is_important:
            self.important_btn.setText("取消重点记忆")
            self.important_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f38ba8;
                    color: #1e1e1e;
                    border-radius: 5px;
                    padding: 5px 10px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #eba0ac;
                }
            """)
        else:
            self.important_btn.setText("标记为重点记忆")
            self.important_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f9e2af;
                    color: #1e1e1e;
                    border-radius: 5px;
                    padding: 5px 10px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #fab387;
                }
            """)
        
        # 保存当前选中的主题索引
        topics = self.memory_lake.memory_index.get("topics", [])
        # 由于UI显示是倒序（最新在前），但存储是正序，需要转换索引
        reversed_topics = list(reversed(topics))
        ui_index = reversed_topics.index(topic_data)
        self.current_topic_index = len(topics) - 1 - ui_index
        
        details = f"主题: {topic_data['topic']}\n"
        details += f"日期: {topic_data['date']}\n"
        details += f"时间: {topic_data['timestamp']}\n"
        details += f"日志文件: {topic_data.get('log_file', 'N/A')}\n"
        
        # 添加具体聊天记录
        conversation_details = topic_data.get('conversation_details', '')
        if conversation_details:
            details += f"\n具体聊天记录:\n{conversation_details}"
        
        self.details_text.setText(details)

    def toggle_important_memory(self):
        """切换重点记忆标记"""
        if not hasattr(self, 'current_topic_index'):
            return
        
        try:
            topics = self.memory_lake.memory_index.get("topics", [])
            if 0 <= self.current_topic_index < len(topics):
                current_topic = topics[self.current_topic_index]
                is_important = current_topic.get("is_important", False)
                
                if is_important:
                    # 取消重点记忆标记
                    if self.memory_lake.unmark_as_important(self.current_topic_index):
                        self.refresh_data()
                        print("✅ 已取消重点记忆标记")
                else:
                    # 添加重点记忆标记
                    if self.memory_lake.mark_as_important(self.current_topic_index):
                        self.refresh_data()
                        print("✅ 已标记为重点记忆")
        except Exception as e:
            print(f"切换重点记忆标记失败: {str(e)}")


class MCPToolsDialog(QDialog):
    """MCP工具管理对话框"""
    
    def __init__(self, mcp_tools, parent=None):
        super().__init__(parent)
        self.mcp_tools = mcp_tools
        self.setWindowTitle("MCP工具管理")
        self.setGeometry(200, 200, 1000, 800)  # 增加窗口高度
        
        # 设置图标
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))
        
        self.init_ui()
        self.refresh_tools()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 工具列表区域
        tools_group = QGroupBox("可用工具")
        tools_group.setStyleSheet("""
            QGroupBox {
                color: #cdd6f4;
                font-size: 14px;
                border: 1px solid #45475a;
                border-radius: 5px;
                margin-top: 2ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #1e1e2e;
            }
        """)
        tools_layout = QVBoxLayout()
        
        # 搜索框和按钮区域
        search_layout = QHBoxLayout()
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索工具...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 12px;
            }
        """)
        self.search_edit.textChanged.connect(self.filter_tools)
        search_layout.addWidget(self.search_edit)
        
        # 按钮区域
        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_tools)
        search_layout.addWidget(refresh_btn)
        
        add_tool_btn = QPushButton("新建工具")
        add_tool_btn.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #eba0ac;
            }
        """)
        add_tool_btn.clicked.connect(self.add_new_tool)
        search_layout.addWidget(add_tool_btn)
        
        tools_layout.addLayout(search_layout)
        
        # 添加一些间距，避免标题被遮挡
        tools_layout.addSpacing(10)
        
        # 工具列表
        self.tools_list = QListWidget()
        self.tools_list.setStyleSheet("""
            QListWidget {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #45475a;
            }
            QListWidget::item:selected {
                background-color: #89b4fa;
                color: #1e1e1e;
            }
        """)
        self.tools_list.itemClicked.connect(self.show_tool_details)
        tools_layout.addWidget(self.tools_list)
        
        tools_group.setLayout(tools_layout)
        
        # 工具详情区域
        details_group = QGroupBox("工具详情")
        details_group.setStyleSheet("""
            QGroupBox {
                color: #cdd6f4;
                font-size: 14px;
                border: 1px solid #45475a;
                border-radius: 5px;
                margin-top: 2ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #1e1e2e;
            }
        """)
        details_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 10px;
                font-size: 12px;
            }
        """)
        details_layout.addWidget(self.details_text)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("测试工具")
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
        """)
        self.test_btn.clicked.connect(self.test_tool)
        button_layout.addWidget(self.test_btn)
        
        self.edit_btn = QPushButton("编辑工具")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9e2af;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #fab387;
            }
        """)
        self.edit_btn.clicked.connect(self.edit_tool)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("删除工具")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #eba0ac;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_tool)
        button_layout.addWidget(self.delete_btn)
        
        details_layout.addLayout(button_layout)
        details_group.setLayout(details_layout)
        
        # 使用QSplitter来更好地控制布局
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(tools_group)
        splitter.addWidget(details_group)
        splitter.setSizes([600, 400])  # 设置初始大小比例
        
        layout.addWidget(splitter)
        
        self.setLayout(layout)
    
    def refresh_tools(self):
        """刷新工具列表"""
        try:
            # 使用同步方法获取工具列表
            tools = self.mcp_tools.list_tools()
            
            self.tools_list.clear()
            
            # 添加内置工具
            for tool in tools:
                item = QListWidgetItem(f"🔧 {tool}")
                item.setData(Qt.UserRole, tool)
                item.setData(Qt.UserRole + 1, "builtin")  # 标记为内置工具
                self.tools_list.addItem(item)
            
            # 添加自定义工具
            custom_tools = self.load_custom_tools()
            for tool_name in custom_tools.keys():
                item = QListWidgetItem(f"⚙️ {tool_name}")
                item.setData(Qt.UserRole, tool_name)
                item.setData(Qt.UserRole + 1, "custom")  # 标记为自定义工具
                self.tools_list.addItem(item)
                
        except Exception as e:
            print(f"刷新工具列表失败: {str(e)}")
    
    def filter_tools(self):
        """过滤工具"""
        search_text = self.search_edit.text().lower()
        for i in range(self.tools_list.count()):
            item = self.tools_list.item(i)
            item.setHidden(search_text not in item.text().lower())
    
    def show_tool_details(self, item):
        """显示工具详情"""
        tool_name = item.data(Qt.UserRole)
        tool_type = item.data(Qt.UserRole + 1)
        if not tool_name:
            return
        
        try:
            details = f"工具名称: {tool_name}\n"
            details += f"工具类型: {'内置工具' if tool_type == 'builtin' else '自定义工具'}\n"
            
            if tool_type == "builtin":
                # 内置工具 - 现在允许编辑
                info = self.mcp_tools.server.get_tool_info(tool_name)
                if info:
                    details += f"描述: {info.get('description', '无描述')}\n"
                else:
                    details += "描述: 无描述\n"
                details += "注意: 内置工具可以编辑，编辑后会创建自定义版本\n"
            else:
                # 自定义工具
                custom_tools = self.load_custom_tools()
                if tool_name in custom_tools:
                    tool_info = custom_tools[tool_name]
                    details += f"描述: {tool_info.get('description', '无描述')}\n"
                    details += f"代码长度: {len(tool_info.get('code', ''))} 字符\n"
                else:
                    details += "描述: 无描述\n"
            
            self.details_text.setText(details)
        except Exception as e:
            self.details_text.setText(f"获取工具信息失败: {str(e)}")
    
    def test_tool(self):
        """测试选中的工具"""
        current_item = self.tools_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个工具")
            return
        
        tool_name = current_item.data(Qt.UserRole)
        if not tool_name:
            return
        
        # 根据工具类型提供不同的测试参数
        test_params = self.get_test_params(tool_name)
        
        try:
            # 使用同步方法调用工具
            result = self.mcp_tools.server.call_tool(tool_name, **test_params)
            QMessageBox.information(self, "测试结果", f"工具 {tool_name} 测试结果:\n\n{result}")
        except Exception as e:
            QMessageBox.warning(self, "测试失败", f"测试工具失败: {str(e)}")
    
    def get_test_params(self, tool_name):
        """获取工具的测试参数"""
        test_params = {
            "get_system_info": {},
            "list_files": {"directory": "."},
            "read_file": {"file_path": "README.md"},
            "write_file": {"file_path": "test.txt", "content": "测试内容"},
            "execute_command": {"command": "echo Hello World"},
            "get_process_list": {},
            "create_note": {"title": "测试笔记", "content": "这是一个测试笔记"},
            "list_notes": {},
            "search_notes": {"keyword": "测试"},
            "get_weather_info": {"city": "北京"},
            "calculate_distance": {"location1": "北京", "location2": "上海"},
            "calculate": {"expression": "2+2"},
            "get_memory_stats": {},
            "高德mcp": {"location1": "北京", "location2": "上海"}
        }
        
        return test_params.get(tool_name, {})
    
    def add_new_tool(self):
        """新建工具"""
        dialog = AddToolDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            tool_name = dialog.tool_name_edit.text().strip()
            tool_description = dialog.tool_description_edit.toPlainText().strip()
            tool_code = dialog.tool_code_edit.toPlainText().strip()
            
            if tool_name and tool_code:
                # 保存到自定义工具文件
                self.save_custom_tool(tool_name, tool_description, tool_code)
                self.refresh_tools()
                QMessageBox.information(self, "成功", f"工具 '{tool_name}' 已创建")
    
    def edit_tool(self):
        """编辑工具"""
        current_item = self.tools_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个工具")
            return
        
        tool_name = current_item.data(Qt.UserRole)
        tool_type = current_item.data(Qt.UserRole + 1)
        if not tool_name:
            return
        
        if tool_type == "custom":
            # 自定义工具
            custom_tools = self.load_custom_tools()
            if tool_name in custom_tools:
                tool_info = custom_tools[tool_name]
                dialog = AddToolDialog(self, tool_name, tool_info['description'], tool_info['code'])
                if dialog.exec_() == QDialog.Accepted:
                    new_name = dialog.tool_name_edit.text().strip()
                    new_description = dialog.tool_description_edit.toPlainText().strip()
                    new_code = dialog.tool_code_edit.toPlainText().strip()
                    
                    if new_name and new_code:
                        # 删除旧工具，保存新工具
                        self.delete_custom_tool(tool_name)
                        self.save_custom_tool(new_name, new_description, new_code)
                        self.refresh_tools()
                        QMessageBox.information(self, "成功", f"工具 '{tool_name}' 已更新")
        else:
            # 内置工具 - 现在允许编辑
            try:
                # 获取内置工具的代码
                builtin_code = self.get_builtin_tool_code(tool_name)
                if builtin_code:
                    dialog = AddToolDialog(self, tool_name, f"内置工具: {tool_name}", builtin_code)
                    if dialog.exec_() == QDialog.Accepted:
                        new_code = dialog.tool_code_edit.toPlainText().strip()
                        if new_code:
                            # 更新内置工具代码
                            self.update_builtin_tool_code(tool_name, new_code)
                            self.refresh_tools()
                            QMessageBox.information(self, "成功", f"内置工具 '{tool_name}' 已更新")
                else:
                    QMessageBox.warning(self, "警告", f"无法获取内置工具 '{tool_name}' 的代码")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"编辑内置工具失败: {str(e)}")
    
    def get_builtin_tool_code(self, tool_name):
        """获取内置工具的代码"""
        try:
            # 这里可以根据工具名称返回对应的代码模板
            if tool_name == "calculate_distance":
                return '''def calculate_distance(location1, location2):
    """计算两个地点之间的距离（使用高德地图API）"""
    try:
        # 高德地图API密钥 - 直接从配置文件读取最新值
        api_key = self.get_latest_amap_key()
        if not api_key or api_key == "mykey":
            return "高德地图API密钥未配置，请在设置中配置高德地图API密钥"
        
        # 地理编码API获取坐标
        def get_coordinates(address):
            url = "https://restapi.amap.com/v3/geocode/geo"
            params = {
                "address": address,
                "key": api_key,
                "output": "json"
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data["status"] == "1" and data["geocodes"]:
                location = data["geocodes"][0]["location"]
                return location.split(",")
            return None
        
        # 获取两个地点的坐标
        coords1 = get_coordinates(location1)
        coords2 = get_coordinates(location2)
        
        if not coords1 or not coords2:
            return f"无法获取地点坐标：{location1} 或 {location2}"
        
        # 计算直线距离
        from math import radians, cos, sin, asin, sqrt
        
        def haversine_distance(lat1, lon1, lat2, lon2):
            """使用Haversine公式计算两点间的直线距离"""
            # 将经纬度转换为弧度
            lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
            
            # Haversine公式
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371  # 地球半径（公里）
            return c * r
        
        distance = haversine_distance(coords1[1], coords1[0], coords2[1], coords2[0])
        
        result = {
            "location1": location1,
            "location2": location2,
            "coordinates1": coords1,
            "coordinates2": coords2,
            "distance_km": round(distance, 2),
            "distance_m": round(distance * 1000, 0),
            "calculation_type": "直线距离（Haversine公式）",
            "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"计算距离失败: {str(e)}"'''
            else:
                return f"# 内置工具 {tool_name} 的代码\n# 请在此处编辑代码"
        except:
            return None
    
    def update_builtin_tool_code(self, tool_name, new_code):
        """更新内置工具代码"""
        try:
            # 这里可以更新内置工具的代码
            # 由于内置工具是硬编码的，我们可以将修改后的代码保存到自定义工具中
            custom_tools = self.load_custom_tools()
            custom_tools[f"{tool_name}_modified"] = {
                "description": f"修改后的{tool_name}工具",
                "code": new_code,
                "type": "custom"
            }
            
            with open("custom_tools.json", "w", encoding="utf-8") as f:
                json.dump(custom_tools, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            raise Exception(f"更新内置工具代码失败: {str(e)}")
    
    def delete_tool(self):
        """删除工具"""
        current_item = self.tools_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个工具")
            return
        
        tool_name = current_item.data(Qt.UserRole)
        tool_type = current_item.data(Qt.UserRole + 1)
        if not tool_name:
            return
        
        if tool_type == "custom":
            # 自定义工具
            custom_tools = self.load_custom_tools()
            if tool_name in custom_tools:
                reply = QMessageBox.question(self, "确认删除", f"确定要删除工具 '{tool_name}' 吗？",
                                           QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.delete_custom_tool(tool_name)
                    self.refresh_tools()
                    QMessageBox.information(self, "成功", f"工具 '{tool_name}' 已删除")
        else:
            QMessageBox.information(self, "提示", "内置工具无法删除")
    
    def save_custom_tool(self, tool_name, description, code):
        """保存自定义工具"""
        custom_tools = self.load_custom_tools()
        custom_tools[tool_name] = {
            "description": description,
            "code": code,
            "type": "custom"
        }
        
        # 检查代码中是否有API密钥，如果有则同步到配置文件
        import re
        api_key_pattern = r'["\']([a-f0-9]{32})["\']'
        api_keys = re.findall(api_key_pattern, code)
        
        if api_keys:
            # 使用第一个找到的API密钥
            api_key = api_keys[0]
            try:
                if os.path.exists("ai_agent_config.json"):
                    with open("ai_agent_config.json", "r", encoding="utf-8") as f:
                        config = json.load(f)
                    
                    # 更新高德地图API密钥
                    config["amap_key"] = api_key
                    
                    # 保存更新后的配置
                    with open("ai_agent_config.json", "w", encoding="utf-8") as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
                    
                    # 同时更新config.py中的默认值（如果存在）
                    self.update_config_py_amap_key(api_key)
                    
                    print(f"✅ 已自动同步API密钥到配置文件: {api_key}")
            except Exception as e:
                print(f"⚠️ 同步API密钥失败: {str(e)}")
        
        with open("custom_tools.json", "w", encoding="utf-8") as f:
            json.dump(custom_tools, f, ensure_ascii=False, indent=2)
    
    def delete_custom_tool(self, tool_name):
        """删除自定义工具"""
        custom_tools = self.load_custom_tools()
        if tool_name in custom_tools:
            del custom_tools[tool_name]
            with open("custom_tools.json", "w", encoding="utf-8") as f:
                json.dump(custom_tools, f, ensure_ascii=False, indent=2)
    
    def get_latest_amap_key(self):
        """获取最新的高德地图API密钥"""
        try:
            # 直接从配置文件读取最新值
            if os.path.exists("ai_agent_config.json"):
                with open("ai_agent_config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                    api_key = config.get("amap_key", "")
                    # 如果API密钥为空或为占位符，返回空字符串
                    if not api_key or api_key == "MYKEY" or api_key == "mykey":
                        return ""
                    return api_key
        except Exception as e:
            print(f"读取高德地图API密钥失败: {str(e)}")
        return ""

    def update_config_py_amap_key(self, api_key):
        """更新config.py中的amap_key默认值"""
        try:
            if os.path.exists("config.py"):
                with open("config.py", "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 使用正则表达式更新amap_key的默认值
                import re
                # 匹配 "amap_key": "" 或 "amap_key": "任意内容"
                pattern = r'"amap_key":\s*"[^"]*"'
                replacement = f'"amap_key": "{api_key}"'
                
                new_content = re.sub(pattern, replacement, content)
                
                # 写回文件
                with open("config.py", "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                print(f"✅ 已同步更新config.py中的amap_key默认值: {api_key}")
        except Exception as e:
            print(f"⚠️ 更新config.py失败: {str(e)}")

    def load_custom_tools(self):
        """加载自定义工具"""
        try:
            if os.path.exists("custom_tools.json"):
                with open("custom_tools.json", "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {}


class AddToolDialog(QDialog):
    """新建工具对话框"""
    
    def __init__(self, parent=None, tool_name="", description="", code=""):
        super().__init__(parent)
        self.setWindowTitle("新建工具")
        self.setGeometry(300, 300, 600, 500)
        
        # 从代码中提取API密钥
        self.extracted_api_key = self.extract_api_key_from_code(code)
        
        self.init_ui(tool_name, description, code)
    
    def extract_api_key_from_code(self, code):
        """从代码中提取API密钥"""
        if not code:
            return ""
        
        # 查找常见的API密钥模式
        import re
        
        # 查找双引号包围的API密钥
        double_quote_pattern = r'api_key\s*=\s*"([^"]+)"'
        match = re.search(double_quote_pattern, code)
        if match and match.group(1) != "mykey":
            return match.group(1)
        
        # 查找单引号包围的API密钥
        single_quote_pattern = r"api_key\s*=\s*'([^']+)'"
        match = re.search(single_quote_pattern, code)
        if match and match.group(1) != "mykey":
            return match.group(1)
        
        return ""
    
    def update_config_py_amap_key(self, api_key):
        """更新config.py中的amap_key默认值"""
        try:
            if os.path.exists("config.py"):
                with open("config.py", "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 使用正则表达式更新amap_key的默认值
                import re
                # 匹配 "amap_key": "" 或 "amap_key": "任意内容"
                pattern = r'"amap_key":\s*"[^"]*"'
                replacement = f'"amap_key": "{api_key}"'
                
                new_content = re.sub(pattern, replacement, content)
                
                # 写回文件
                with open("config.py", "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                print(f"✅ 已同步更新config.py中的amap_key默认值: {api_key}")
        except Exception as e:
            print(f"⚠️ 更新config.py失败: {str(e)}")
    
    def init_ui(self, tool_name, description, code):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 工具名称
        name_layout = QHBoxLayout()
        name_label = QLabel("工具名称:")
        name_label.setStyleSheet("color: #cdd6f4; font-size: 12px;")
        self.tool_name_edit = QLineEdit(tool_name)
        self.tool_name_edit.setStyleSheet("""
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 12px;
            }
        """)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.tool_name_edit)
        
        # 工具描述
        desc_label = QLabel("工具描述:")
        desc_label.setStyleSheet("color: #cdd6f4; font-size: 12px;")
        self.tool_description_edit = QTextEdit(description)
        self.tool_description_edit.setMaximumHeight(80)
        self.tool_description_edit.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 12px;
            }
        """)
        
        # 工具代码
        code_label = QLabel("工具代码 (Python函数):")
        code_label.setStyleSheet("color: #cdd6f4; font-size: 12px;")
        
        # 代码编辑区域
        code_layout = QVBoxLayout()
        
        # 快速添加API按钮
        api_layout = QHBoxLayout()
        api_label = QLabel("快速添加API密钥:")
        api_label.setStyleSheet("color: #cdd6f4; font-size: 12px;")
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("输入API密钥，将自动替换代码中的'mykey'")
        # 如果从代码中提取到了API密钥，则显示在输入框中
        if self.extracted_api_key:
            self.api_key_edit.setText(self.extracted_api_key)
        self.api_key_edit.setStyleSheet("""
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 12px;
            }
        """)
        
        self.add_api_btn = QPushButton("替换API密钥")
        self.add_api_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """)
        self.add_api_btn.clicked.connect(self.replace_api_key)
        
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_key_edit)
        api_layout.addWidget(self.add_api_btn)
        
        self.tool_code_edit = QTextEdit(code)
        self.tool_code_edit.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        
        code_layout.addLayout(api_layout)
        code_layout.addWidget(self.tool_code_edit)
        
        # 示例代码
        if not code:
            example_code = '''def my_custom_tool(param1="", param2=""):
    """
    自定义工具示例
    参数:
        param1: 第一个参数
        param2: 第二个参数
    返回:
        字符串结果
    """
    try:
        # 在这里编写你的工具逻辑
        result = f"参数1: {param1}, 参数2: {param2}"
        return f"工具执行成功: {result}"
    except Exception as e:
        return f"工具执行失败: {str(e)}"'''
            self.tool_code_edit.setPlainText(example_code)
        
        # 按钮
        button_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
        """)
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e1e;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #eba0ac;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        # 添加到主布局
        layout.addLayout(name_layout)
        layout.addWidget(desc_label)
        layout.addWidget(self.tool_description_edit)
        layout.addWidget(code_label)
        layout.addLayout(code_layout)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def replace_api_key(self):
        """替换代码中的API密钥"""
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "警告", "请输入API密钥")
            return
        
        current_code = self.tool_code_edit.toPlainText()
        
        # 检查是否有mykey占位符或现有的API密钥
        has_mykey = "mykey" in current_code.lower()
        
        # 检查是否有任何看起来像API密钥的字符串（32位字符）
        import re
        api_key_pattern = r'["\']([a-f0-9]{32})["\']'
        existing_api_keys = re.findall(api_key_pattern, current_code)
        
        if not has_mykey and not existing_api_keys:
            QMessageBox.information(self, "提示", "代码中没有找到'mykey'占位符或现有API密钥")
            return
        
        # 替换所有的"mykey"和现有API密钥为新的API密钥
        new_code = current_code
        if has_mykey:
            new_code = new_code.replace('"mykey"', f'"{api_key}"')
            new_code = new_code.replace("'mykey'", f"'{api_key}'")
            new_code = new_code.replace('"MYKEY"', f'"{api_key}"')
            new_code = new_code.replace("'MYKEY'", f"'{api_key}'")
        
        # 替换所有找到的API密钥
        for old_api_key in existing_api_keys:
            new_code = new_code.replace(f'"{old_api_key}"', f'"{api_key}"')
            new_code = new_code.replace(f"'{old_api_key}'", f"'{api_key}'")
        
        self.tool_code_edit.setPlainText(new_code)
        
        # 同时更新配置文件中的API密钥
        try:
            if os.path.exists("ai_agent_config.json"):
                with open("ai_agent_config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                # 更新高德地图API密钥
                config["amap_key"] = api_key
                
                # 保存更新后的配置
                with open("ai_agent_config.json", "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                
                # 同时更新config.py中的默认值
                self.update_config_py_amap_key(api_key)
                
                QMessageBox.information(self, "成功", f"已成功将代码中的API密钥替换为: {api_key}\n同时已更新配置文件中的高德地图API密钥")
            else:
                QMessageBox.information(self, "成功", f"已成功将代码中的API密钥替换为: {api_key}")
        except Exception as e:
            QMessageBox.warning(self, "警告", f"代码替换成功，但配置文件更新失败: {str(e)}")
