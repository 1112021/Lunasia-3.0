# -*- coding: utf-8 -*-
import sys
import os
import datetime
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QLabel, QProgressBar, QSplitter, QGroupBox, 
                             QFormLayout, QStatusBar, QFileDialog, QDialog, QSizePolicy,
                             QMenu, QAction)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QFont, QPixmap, QIcon

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("⚠️ keyboard 库未安装，全局快捷键功能将不可用")

from ai_agent import AIAgent
from ui_dialogs import SettingsDialog, MemoryLakeDialog, MCPToolsDialog
from file_analysis_tool import FileAnalysisTool
from voice_input import record_to_wav, recognize_wav, is_voice_input_available

class AIAgentApp(QMainWindow):
    """露尼西亚AI助手主窗口"""
    
    # 定义信号
    response_ready = pyqtSignal(str)
    voice_result_ready = pyqtSignal(str, str)  # (text, error_message) 从语音识别线程发到主线程
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.agent = AIAgent(config)
        
        # 初始化文件分析工具
        self.file_analyzer = FileAnalysisTool(config)
        
        # 设置首次介绍标记
        self.first_introduction_given = False
        self.waiting_for_first_response = False
        
        # 初始化UI
        self.init_ui()
        
        # 应用窗口透明度设置
        self.apply_transparency()
        
        # 连接信号
        self.response_ready.connect(self.update_ui_with_response)
        self.voice_result_ready.connect(self._apply_voice_result)
        
        # 启动状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # 每秒更新一次状态
        
        # 设置全局快捷键
        self.setup_global_shortcuts()
        
        # 检查是否是第一次运行，如果是则进行自我介绍
        self.check_first_run_and_introduce()
    
    def apply_transparency(self):
        """应用窗口透明度设置"""
        try:
            transparency = self.config.get("window_transparency", 100)
            if transparency < 100:
                # 将百分比转换为0-1之间的值
                opacity = transparency / 100.0
                self.setWindowOpacity(opacity)
                print(f"✅ 窗口透明度已设置为 {transparency}%")
            else:
                # 100%表示完全不透明
                self.setWindowOpacity(1.0)
        except Exception as e:
            print(f"⚠️ 设置窗口透明度失败: {str(e)}")
    
    def update_transparency(self, value):
        """实时更新窗口透明度（用于设置对话框的实时预览）"""
        try:
            if value < 100:
                # 将百分比转换为0-1之间的值
                opacity = value / 100.0
                self.setWindowOpacity(opacity)
            else:
                # 100%表示完全不透明
                self.setWindowOpacity(1.0)
        except Exception as e:
            print(f"⚠️ 实时更新透明度失败: {str(e)}")

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("露尼西亚AI助手")
        # 增加一点点高度和宽度，让按钮对齐并保持比例
        # 原来：1300x800，现在：1350x850
        # 聊天区域：1000px，右侧区域：350px，高度增加50px
        window_width = 1350  # 增加50px宽度，主要给聊天区域
        window_height = 850  # 增加50px高度，让按钮向下移动对齐
        
        self.setGeometry(100, 100, window_width, window_height)
        
        # 设置窗口尺寸策略，固定大小不可拖拽
        from PyQt5.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(window_width, window_height)  # 固定窗口大小
        
        # 设置窗口样式（含全局 QToolTip：深底白字，保证可读）
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QToolTip {
                background-color: #313244;
                color: #ffffff;
                border: 1px solid #585b70;
                border-radius: 4px;
                padding: 8px 10px;
                font-size: 13px;
            }
        """)
        
        # 创建中央部件
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 聊天区域 (占用3/4宽度)
        chat_widget = QWidget()
        chat_widget.setStyleSheet("background-color: #1e1e2e; border-radius: 10px;")
        chat_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        chat_layout = QVBoxLayout()
        chat_layout.setSpacing(10)
        chat_layout.setContentsMargins(10, 10, 10, 10)
        
        # 聊天历史
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: none;
                border-style: none;
                outline: none;
                padding: 10px;
                font-family: 'Microsoft YaHei UI', sans-serif;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: none;
                border-style: none;
                outline: none;
            }
        """)
        
        # 输入区域
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入消息...")
        self.input_edit.returnPressed.connect(self.send_message_shortcut)
        self.input_edit.setStyleSheet("""
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 15px;
                padding: 10px 15px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #89b4fa;
            }
        """)

        # 语音输入按钮（长按录音，松开识别）：默认无背景，录音时填充颜色
        self._voice_stop_event = None
        self._voice_record_thread = None
        self._mic_btn_style_idle = """
            QPushButton {
                background-color: #ffffff;
                color: #1e1e1e;
                border: 1px solid #45475a;
                border-radius: 15px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(166, 227, 161, 0.5);
                border: 1px solid #585b70;
            }
        """
        self._mic_btn_style_active = """
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e1e;
                border-radius: 15px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
        """
        self.mic_btn = QPushButton()
        mic_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "mic_icon.png")
        if os.path.isfile(mic_icon_path):
            self.mic_btn.setIcon(QIcon(mic_icon_path))
            self.mic_btn.setIconSize(QSize(24, 24))
        else:
            self.mic_btn.setText("🎤")
        self.mic_btn.setToolTip("长按录音，松开后识别为文字（需配置语音识别 API 密钥）")
        self.mic_btn.pressed.connect(self._on_voice_pressed)
        self.mic_btn.released.connect(self._on_voice_released)
        self.mic_btn.setStyleSheet(self._mic_btn_style_idle)

        # 文件上传按钮
        upload_btn = QPushButton("➕")
        upload_btn.setToolTip("上传文件")
        upload_btn.clicked.connect(self.show_upload_menu)
        upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9e2af;
                color: #1e1e1e;
                border-radius: 15px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #e7d19e;
            }
        """)

        send_btn = QPushButton("发送")
        # 根据配置设置快捷键
        send_key_mode = self.config.get("send_key_mode", "Ctrl+Enter")
        if send_key_mode == "Enter":
            send_btn.setShortcut("Return")
        else:
            send_btn.setShortcut("Ctrl+Return")
        send_btn.clicked.connect(self.send_message)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e1e;
                border-radius: 15px;
                padding: 10px 20px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """)

        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #45475a;
                border-radius: 5px;
                text-align: center;
                background-color: #313244;
                color: #cdd6f4;
            }
            QProgressBar::chunk {
                background-color: #89b4fa;
                border-radius: 3px;
            }
        """)

        # 创建水平布局，让输入元素与右侧按钮对齐
        input_container = QHBoxLayout()
        input_container.setSpacing(10)
        
        input_container.addWidget(self.input_edit)
        input_container.addWidget(self.mic_btn)
        input_container.addWidget(upload_btn)
        input_container.addWidget(send_btn)
        input_container.addWidget(self.progress_bar)

        chat_layout.addWidget(self.chat_history, 3)
        chat_layout.addStretch()  # 添加弹性空间，让输入区域向下移动
        chat_layout.addLayout(input_container, 1)
        chat_widget.setLayout(chat_layout)

        # 右侧预留区域 (占用1/4宽度，用于Live2D)
        right_widget = QWidget()
        right_widget.setStyleSheet("background-color: #1e1e2e; border-radius: 10px;")
        right_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(5)  # 进一步减少间距，让半身像更接近状态栏
        right_layout.setContentsMargins(10, 8, 10, 8)  # 减少上下边距，让按钮更接近底部
        right_layout.addStretch()  # 添加弹性空间，让按钮推到底部

        # 状态信息
        status_group = QGroupBox("")
        status_group.setStyleSheet("""
            QGroupBox {
                color: #cdd6f4;
                font-size: 10px;
                border: 1px solid #45475a;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
                padding-bottom: 10px;
                max-width: 320px;
                min-width: 320px;
                min-height: 120px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 4px 8px;
                background-color: #1e1e2e !important;
                font-size: 12px !important;
                font-weight: bold !important;
                color: #ffffff !important;
                font-family: "Microsoft YaHei", "SimHei", sans-serif !important;
                border: 1px solid #1e1e2e !important;
                border-radius: 3px !important;
                margin-top: 3px !important;
                margin-bottom: 3px !important;
            }
        """)
        status_layout = QFormLayout()
        status_layout.setVerticalSpacing(12)  # 进一步增加垂直间距，配合更大的字体
        status_layout.setHorizontalSpacing(8)  # 增加水平间距，配合更大的字体
        
        # 设置标签样式
        status_layout.setLabelAlignment(Qt.AlignRight)

        # 创建标签样式
        label_style = "color: #cdd6f4; font-size: 14px; font-weight: bold; font-family: 'Microsoft YaHei', 'SimHei', sans-serif;"
        value_style = "color: #a6e3a1; font-size: 14px; font-weight: bold; font-family: 'Microsoft YaHei', 'SimHei', sans-serif;"
        
        # 当前模型
        model_label = QLabel("当前模型:")
        model_label.setStyleSheet(label_style)
        model_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ai_model = QLabel(self.config.get("selected_model", "deepseek-reasoner"))
        self.ai_model.setStyleSheet(value_style)
        status_layout.addRow(model_label, self.ai_model)

        # 记忆系统
        memory_label = QLabel("记忆系统:")
        memory_label.setStyleSheet(label_style)
        memory_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ai_memory = QLabel("识底深湖")
        self.ai_memory.setStyleSheet(value_style)
        status_layout.addRow(memory_label, self.ai_memory)

        # 预加载应用
        apps_label = QLabel(" 预载应用:")  # 在开头添加一个空格，向右移动一个字节
        apps_label.setStyleSheet(label_style)
        apps_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 确保右对齐和垂直居中
        self.ai_apps = QLabel(f"{getattr(self.agent, 'app_count', 0)}")
        self.ai_apps.setStyleSheet(value_style)
        status_layout.addRow(apps_label, self.ai_apps)

        # 登录位置
        location_label = QLabel("登录位置:")
        location_label.setStyleSheet(label_style)
        location_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ai_location = QLabel(getattr(self.agent, 'location', '未知'))
        self.ai_location.setStyleSheet(value_style)
        status_layout.addRow(location_label, self.ai_location)

        # 当前时间
        time_label = QLabel("当前时间:")
        time_label.setStyleSheet(label_style)
        time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ai_time = QLabel("同步中...")
        self.ai_time.setStyleSheet(value_style)
        status_layout.addRow(time_label, self.ai_time)
        
        # 启动时间同步
        self.sync_time()

        status_group.setLayout(status_layout)


        # 露尼西亚半身像区域
        live2d_label = QLabel()
        live2d_label.setAlignment(Qt.AlignCenter)
        live2d_label.setScaledContents(False)  # 不自动缩放，保持原始比例
        live2d_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)  # 固定尺寸，防止拉伸
        live2d_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e2e;
                border: 2px solid #89b4fa;
                border-radius: 15px;
                padding: 5px;
            }
        """)
        
        # 加载露尼西亚图片
        try:
            pixmap = QPixmap("Lunesia.png")
            if not pixmap.isNull():
                # 重新计算适合增加高度后的9:16比例尺寸
                # 系统状态栏宽度固定为320px，露尼西亚图片宽度也要320px
                # 窗口高度增加到900px，为Live2D区域提供更多垂直空间
                # 为了保持9:16比例，高度 = 320*(16/9) = 569px
                target_width = 320
                target_height = int(target_width * 16 / 9)  # 569px
                
                # 缩放图片到目标尺寸，保持宽高比
                scaled_pixmap = pixmap.scaled(target_width, target_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                live2d_label.setPixmap(scaled_pixmap)
                
                # 设置固定尺寸，确保不与其他元素重合
                live2d_label.setFixedSize(target_width, target_height)  # 使用固定尺寸，防止挤压其他元素
                print(f"✅ 成功加载露尼西亚半身像，尺寸: {target_width}x{target_height}")
            else:
                print("❌ 无法加载Lunesia.png图片")
                live2d_label.setText("图片加载失败")
                live2d_label.setStyleSheet("""
                    QLabel {
                        background-color: #1e1e2e;
                        color: #cdd6f4;
                        border: 2px solid #f38ba8;
                        border-radius: 15px;
                        font-size: 18px;
                        padding: 20px;
                    }
                """)
        except Exception as e:
            print(f"❌ 加载图片时出错: {e}")
            live2d_label.setText("图片加载失败")
            live2d_label.setStyleSheet("""
                QLabel {
                    background-color: #1e1e2e;
                    color: #cdd6f4;
                    border: 2px solid #f38ba8;
                    border-radius: 15px;
                    font-size: 18px;
                    padding: 20px;
                }
            """)

        # 按钮区域
        button_layout = QHBoxLayout()

        # 设置按钮
        settings_btn = QPushButton("设置")
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9e2af;
                color: #1e1e1e;
                border-radius: 10px;
                padding: 10px 15px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #e7d19e;
            }
        """)
        settings_btn.clicked.connect(self.open_settings)
        
        # 识底深湖按钮
        memory_btn = QPushButton("识底深湖")
        memory_btn.setStyleSheet("""
            QPushButton {
                background-color: #cba6f7;
                color: #1e1e1e;
                border-radius: 10px;
                padding: 10px 15px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
        """)
        memory_btn.clicked.connect(self.open_memory_lake)
        
        # MCP工具按钮
        mcp_btn = QPushButton("MCP工具")
        mcp_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e1e;
                border-radius: 10px;
                padding: 10px 15px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
        """)
        mcp_btn.clicked.connect(self.open_mcp_tools)

        button_layout.addWidget(settings_btn)
        button_layout.addWidget(memory_btn)
        button_layout.addWidget(mcp_btn)

        right_layout.addWidget(status_group)
        right_layout.addWidget(live2d_label)  # 移除stretch参数，让图片按实际尺寸显示
        right_layout.addLayout(button_layout)
        right_widget.setLayout(right_layout)

        # 添加分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(chat_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([1000, 350])  # 增加聊天区域宽度，右侧保持不变
        # 禁用分割器拖拽功能
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        # 设置分割器保持等比例缩放
        splitter.setStretchFactor(0, 1)  # 聊天区域可拉伸
        splitter.setStretchFactor(1, 0)  # 右侧区域固定比例

        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 添加状态栏
        self.statusBar().showMessage("就绪")
        
        # 显示启动欢迎信息
        location = getattr(self.agent, 'location', '未知')
        app_count = getattr(self.agent, 'app_count', 0)
        self.add_message("系统", f"登录地址：{location}，预载应用：{app_count}个")

    def add_message(self, sender, message):
        """添加消息到聊天历史"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {sender}: {message}\n"
        
        # 获取当前文本并添加新消息
        current_text = self.chat_history.toPlainText()
        new_text = current_text + formatted_msg
        self.chat_history.setPlainText(new_text)
        
        # 滚动到底部
        self.chat_history.verticalScrollBar().setValue(
            self.chat_history.verticalScrollBar().maximum()
        )
    

    def show_upload_menu(self):
        """显示文件上传选择菜单"""
        # 创建菜单
        menu = QMenu(self)
        
        # 添加图片上传选项
        image_action = QAction("📷 上传图片", self)
        image_action.triggered.connect(self.send_image)
        menu.addAction(image_action)
        
        # 添加视频上传选项
        video_action = QAction("🎬 上传视频", self)
        video_action.triggered.connect(self.send_video)
        menu.addAction(video_action)
        
        # 添加文件上传选项
        file_action = QAction("📄 上传文件", self)
        file_action.triggered.connect(self.send_file)
        menu.addAction(file_action)
        
        # 显示菜单
        button = self.sender()
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))
    
    def send_file(self):
        """上传并分析文件（PDF、CSV、Excel、Word、代码等）"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            "支持的文件 (*.pdf *.csv *.xlsx *.xls *.docx *.doc *.py *.java *.js *.jsx *.ts *.tsx *.cpp *.c *.h *.go *.rs);;"
            "文档文件 (*.pdf *.docx *.doc);;"
            "表格文件 (*.csv *.xlsx *.xls);;"
            "Python代码 (*.py);;"
            "Java代码 (*.java);;"
            "JavaScript/TypeScript (*.js *.jsx *.ts *.tsx);;"
            "C/C++代码 (*.c *.cpp *.h *.hpp);;"
            "其他代码 (*.go *.rs);;"
            "所有文件 (*.*)"
        )
        
        if file_path:
            self.add_message("指挥官", f"📄 上传文件: {file_path}")
            
            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("分析文件中... 0%")
            
            # 启动进度条更新定时器
            self.progress_timer = QTimer()
            self.progress_timer.timeout.connect(self.update_progress)
            self.progress_timer.start(30)
            self.progress_value = 0
            
            # 添加超时保护
            self.timeout_timer = QTimer()
            self.timeout_timer.timeout.connect(self.handle_timeout)
            self.timeout_timer.start(120000)  # 120秒超时
            
            # 在单独的线程中处理文件分析
            threading.Thread(target=self.process_file_analysis, args=(file_path,), daemon=True).start()
    
    def process_file_analysis(self, file_path):
        """处理文件分析"""
        try:
            print(f"📄 开始分析文件: {file_path}")
            
            # 🔥 使用agent的process_file_upload方法，确保文件上下文被保存
            analysis_report = self.agent.process_file_upload(file_path)
            
            # 发送分析结果
            self.response_ready.emit(analysis_report)
                
        except Exception as e:
            error_msg = f"❌ 文件分析出错: {str(e)}"
            print(error_msg)
            self.response_ready.emit(error_msg)
        finally:
            # 停止进度条
            if hasattr(self, 'progress_timer'):
                self.progress_timer.stop()
            if hasattr(self, 'timeout_timer'):
                self.timeout_timer.stop()
            
            # 隐藏进度条
            self.progress_bar.setVisible(False)

    def send_image(self):
        """上传并分析图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片文件",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp *.tiff *.webp)"
        )

        if file_path:
            self.add_message("指挥官", f"📷 上传图片: {file_path}")

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("分析图片中... 0%")

            # 启动进度条更新定时器
            self.progress_timer = QTimer()
            self.progress_timer.timeout.connect(self.update_progress)
            self.progress_timer.start(30)
            self.progress_value = 0

            # 添加超时保护
            self.timeout_timer = QTimer()
            self.timeout_timer.timeout.connect(self.handle_timeout)
            self.timeout_timer.start(180000)  # 180秒超时，给图片分析更多时间

            # 在单独的线程中处理图片分析
            threading.Thread(target=self.process_image_analysis, args=(file_path,), daemon=True).start()

    def process_image_analysis(self, file_path):
        """处理图片分析"""
        try:
            print(f"🖼️ 开始分析图片: {file_path}")

            # 获取图片分析结果
            response = self.agent.process_image(file_path)

            print(f"✅ 图片分析完成: {response[:50]}...")

            # 确保响应不为空
            if not response or response.strip() == "":
                response = "抱歉，图片分析失败，请重试。"

            # 🔥 保存到识底深湖记忆系统
            user_input = f"📷 上传图片: {os.path.basename(file_path)}"
            self.agent._update_memory_lake(user_input, response)
            print(f"💾 图片分析已保存到识底深湖记忆系统")

            # 发送信号到主线程
            self.response_ready.emit(response)

        except Exception as e:
            print(f"❌ 图片分析错误: {str(e)}")
            error_response = f"抱歉，图片分析时出现了问题：{str(e)}"
            self.response_ready.emit(error_response)

    def send_video(self):
        """上传并分析视频"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.webm *.m4v *.3gp)"
        )

        if file_path:
            self.add_message("指挥官", f"🎬 上传视频: {file_path}")

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("分析视频中... 0%")

            # 启动进度条更新定时器
            self.progress_timer = QTimer()
            self.progress_timer.timeout.connect(self.update_progress)
            self.progress_timer.start(30)
            self.progress_value = 0

            # 添加超时保护（视频分析可能需要较长时间，特别是大文件分段分析）
            self.timeout_timer = QTimer()
            self.timeout_timer.timeout.connect(self.handle_timeout)
            self.timeout_timer.start(600000)  # 10分钟超时

            # 在单独的线程中处理视频分析
            threading.Thread(target=self.process_video_analysis, args=(file_path,), daemon=True).start()

    def process_video_analysis(self, file_path):
        """处理视频分析"""
        try:
            print(f"🎬 开始分析视频: {file_path}")

            # 获取视频分析结果
            response = self.agent.process_video(file_path)

            print(f"✅ 视频分析完成: {response[:50]}...")

            # 确保响应不为空
            if not response or response.strip() == "":
                response = "抱歉，视频分析失败，请重试。"

            # 🔥 检查是否是分段分析结果，如果是则需要传递给主agent整合
            if "[SEGMENTED_VIDEO_ANALYSIS]" in response:
                print("🎬 [视频分析] 检测到分段分析结果，将传递给主agent整合")
                # 移除标记，保留内容
                video_content = response.replace("[SEGMENTED_VIDEO_ANALYSIS]\n", "").replace("[SEGMENTED_VIDEO_ANALYSIS]", "")
                # 构造整合请求，让主agent处理
                integration_prompt = video_content
                # 通过主agent处理整合请求（跳过框架agent和记忆保存，直接使用主agent）
                print("🎬 [视频分析] 调用主agent整合分段分析结果...")
                response = self.agent.process_command(integration_prompt, skip_framework=True, suppress_tool_routing=True, skip_memory_save=True)
                print(f"✅ 主agent整合完成: {response[:50]}...")

            # 🔥 保存到识底深湖记忆系统
            user_input = f"🎬 上传视频: {os.path.basename(file_path)}"
            self.agent._update_memory_lake(user_input, response)
            print(f"💾 视频分析已保存到识底深湖记忆系统")

            # 发送信号到主线程
            self.response_ready.emit(response)

        except Exception as e:
            print(f"❌ 视频分析错误: {str(e)}")
            error_response = f"抱歉，视频分析时出现了问题：{str(e)}"
            self.response_ready.emit(error_response)

    def _voice_worker(self, stop_event):
        """后台：录音 → 识别 → 主线程更新输入框"""
        text, err = "", None
        wav_path = None
        try:
            print("[语音] 后台线程已启动", flush=True)
            wav_path, rec_err = record_to_wav(stop_event)
            print("[语音] 录音已结束, rec_err=%s" % (rec_err or "无"), flush=True)
            if rec_err:
                self.voice_result_ready.emit("", rec_err)
                return
            api_key = self.config.get("dashscope_key", "").strip() or None
            print("[语音] 开始调用识别 API...", flush=True)
            text, asr_err = recognize_wav(wav_path, api_key=api_key)
            err = asr_err
            print("[语音] 识别 API 返回, text_len=%s, err=%s" % (len(text or ""), err or "无"), flush=True)
        except Exception as e:
            err = "识别过程异常: " + str(e)
            print("[语音] 异常: %s" % e, flush=True)
        finally:
            try:
                if wav_path and os.path.isfile(wav_path):
                    os.unlink(wav_path)
            except Exception:
                pass
        t, e = text or "", err
        print("[语音] 已通过信号通知主线程更新 UI", flush=True)
        self.voice_result_ready.emit(t, e)

    def _apply_voice_result(self, text, error_message):
        """在主线程中把语音识别结果写入输入框或提示错误"""
        print("[语音] _apply_voice_result 被调用, error_message=%s" % (error_message or "无"), flush=True)
        self._voice_record_thread = None
        if hasattr(self, 'mic_btn') and self.mic_btn:
            self.mic_btn.setStyleSheet(self._mic_btn_style_idle)
        if error_message:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "语音识别", error_message)
            print(f"⚠️ 语音识别失败: {error_message}")
            return
        if text:
            cur = self.input_edit.text()
            self.input_edit.setText((cur + " " + text).strip() if cur else text)
            print(f"✅ 语音识别结果: {text[:50]}{'...' if len(text) > 50 else ''}")
            if self.config.get("voice_auto_send", False):
                self.send_message()
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "语音识别", "未识别到语音或录音过短，请长按麦克风说话后松开重试。")
            print("ℹ️ 语音识别结果为空")

    def _on_voice_pressed(self):
        """按下麦克风：开始录音（后台线程阻塞直到 release 触发 stop_event）"""
        if not is_voice_input_available():
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "语音输入",
                "语音输入不可用：请安装 pyaudio 与 dashscope，并在设置中配置语音识别 API 密钥。"
            )
            return
        if self._voice_record_thread and self._voice_record_thread.is_alive():
            return
        if hasattr(self, 'mic_btn') and self.mic_btn:
            self.mic_btn.setStyleSheet(self._mic_btn_style_active)
        self._voice_stop_event = threading.Event()
        self._voice_record_thread = threading.Thread(
            target=self._voice_worker,
            args=(self._voice_stop_event,),
            daemon=True,
        )
        self._voice_record_thread.start()

    def _on_voice_released(self):
        """松开麦克风：停止录音，后台线程会完成识别并更新输入框"""
        if self._voice_stop_event:
            self._voice_stop_event.set()
        if hasattr(self, 'mic_btn') and self.mic_btn:
            self.mic_btn.setStyleSheet(self._mic_btn_style_idle)

    def send_message(self):
        """发送消息"""
        user_input = self.input_edit.text().strip()
        if not user_input:
            return

        self.add_message("指挥官", user_input)
        self.input_edit.clear()

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("处理中... 0%")

        # 启动进度条更新定时器
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.start(30)  # 每30毫秒更新一次，更平滑
        self.progress_value = 0
        
        # 添加超时保护，防止进度条无限卡住
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self.handle_timeout)
        
        # 检查是否是安全测试请求，设置更长的超时时间
        is_security_test = any(keyword in user_input.lower() for keyword in [
            '获取', '账号', '密码', '登录', '攻击', '注入', '漏洞', '测试', '扫描', '破解'
        ])
        
        if is_security_test:
            self.timeout_timer.start(600000)  # 600秒超时，给安全测试更多时间
            print("🔒 检测到安全测试请求，设置600秒超时")
        else:
            self.timeout_timer.start(240000)  # 240秒超时，给AI更多时间

        # 在单独的线程中处理响应
        threading.Thread(target=self.process_ai_response, args=(user_input,), daemon=True).start()

    def send_message_shortcut(self):
        """快捷键发送消息"""
        send_key_mode = self.config.get("send_key_mode", "Ctrl+Enter")
        
        if send_key_mode == "Enter":
            # Enter模式：直接发送
            self.send_message()
        else:
            # Ctrl+Enter模式：需要按住Ctrl
            if QApplication.keyboardModifiers() & Qt.ControlModifier:
                self.send_message()

    def process_ai_response(self, user_input):
        """处理AI响应"""
        try:
            print(f"🔄 开始处理AI响应: {user_input}")
            
            # 检查是否是安全测试请求
            is_security_test = any(keyword in user_input.lower() for keyword in [
                '获取', '账号', '密码', '登录', '攻击', '注入', '漏洞', '测试', '扫描', '破解'
            ])
            
            if is_security_test:
                # 安全测试使用流式进度更新
                self._process_security_test_with_progress(user_input)
            else:
                # 普通AI响应
                response = self.agent.process_command(user_input, self.waiting_for_first_response)
                
                # 如果这是首次响应，重置标记
                if self.waiting_for_first_response:
                    self.waiting_for_first_response = False
                
                print(f"✅ AI响应获取成功: {response[:50]}...")
                
                # 确保响应不为空
                if not response or response.strip() == "":
                    response = "抱歉，我没有理解您的意思，请重新表述一下。"

                # 发送信号到主线程
                print(f"📡 发送信号: {response[:50]}...")
                self.response_ready.emit(response)
            
        except Exception as e:
            # 如果出现异常，也要更新UI
            print(f"❌ AI响应处理错误: {str(e)}")
            error_response = f"抱歉，处理您的请求时出现了问题：{str(e)}"
            self.response_ready.emit(error_response)
    
    def _process_security_test_with_progress(self, user_input):
        """处理安全测试请求"""
        try:
            # 执行安全测试
            response = self.agent.process_command(user_input, self.waiting_for_first_response)
            
            # 如果这是首次响应，重置标记
            if self.waiting_for_first_response:
                self.waiting_for_first_response = False
            
            print(f"✅ 安全测试完成: {response[:50]}...")
            
            # 发送最终结果
            self.response_ready.emit(response)
            
        except Exception as e:
            print(f"❌ 安全测试处理错误: {str(e)}")
            error_response = f"抱歉，安全测试过程中出现了问题：{str(e)}"
            self.response_ready.emit(error_response)

    def update_progress(self):
        """更新进度条"""
        if hasattr(self, 'progress_value'):
            # 检查是否是图片分析
            is_image_analysis = "分析图片中" in self.progress_bar.format()
            
            if is_image_analysis:
                # 图片分析使用更慢的进度增长
                if self.progress_value < 20:
                    self.progress_value += 0.5  # 前20%很慢增长
                elif self.progress_value < 50:
                    self.progress_value += 0.3  # 中间30%极慢增长
                elif self.progress_value < 80:
                    self.progress_value += 0.2  # 后30%极慢增长
                else:
                    self.progress_value = 80  # 最多到80%，留20%给完成时
            else:
                # 普通对话使用正常进度增长
                if self.progress_value < 30:
                    self.progress_value += 2  # 前30%快速增长
                elif self.progress_value < 70:
                    self.progress_value += 1  # 中间40%中等速度
                elif self.progress_value < 85:
                    self.progress_value += 0.5  # 后15%慢速增长
                else:
                    self.progress_value = 85  # 最多到85%，留15%给完成时
            
            self.progress_bar.setValue(int(self.progress_value))
            current_format = self.progress_bar.format()
            if "分析图片中" in current_format:
                self.progress_bar.setFormat(f"分析图片中... {int(self.progress_value)}%")
            else:
                self.progress_bar.setFormat(f"处理中... {int(self.progress_value)}%")

    def update_ui_with_response(self, response):
        """在主线程中更新UI"""
        print(f"🔄 开始更新UI: {response[:50]}...")
        print(f"🔄 完整消息: {response}")
        
        # 停止所有定时器
        if hasattr(self, 'progress_timer'):
            self.progress_timer.stop()
        if hasattr(self, 'timeout_timer'):
            self.timeout_timer.stop()
        
        # 立即完成进度条
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("完成")
        
        # 添加消息到聊天历史
        print(f"📝 添加消息到聊天历史: 露尼西亚 - {response[:50]}...")
        self.add_message("露尼西亚", response)
        
        # 延迟隐藏进度条
        QTimer.singleShot(800, lambda: self.progress_bar.setVisible(False))

    def handle_timeout(self):
        """处理超时"""
        print("⏰ 处理超时")
        
        # 停止安全测试进度更新
        self.stop_security_progress_update()
        
        # 检查是否是图片分析
        is_image_analysis = "分析图片中" in self.progress_bar.format()
        
        # 检查是否是安全测试
        is_security_test = "安全测试" in self.progress_bar.format() or "攻击" in self.progress_bar.format()
        
        if is_image_analysis:
            timeout_message = "抱歉，图片分析时间过长，请稍后重试。如果图片较大或内容复杂，可能需要更长时间处理。"
        elif is_security_test:
            timeout_message = "安全测试时间过长，请稍后重试。深度安全测试需要更多时间来完成。"
        else:
            timeout_message = "抱歉，处理时间过长，请重试。"
        
        self.response_ready.emit(timeout_message)


    def start_security_progress_update(self):
        """启动安全测试进度更新"""
        self.security_progress_timer = QTimer()
        self.security_progress_timer.timeout.connect(self.update_security_progress)
        self.security_progress_timer.start(5000)  # 每5秒更新一次
        self.security_progress_step = 0
    
    def update_security_progress(self):
        """更新安全测试进度"""
        self.security_progress_step += 1
        
        progress_messages = [
            "🔍 正在进行端口扫描...",
            "🌐 正在分析Web服务...",
            "🔍 正在执行漏洞扫描...",
            "💉 正在测试SQL注入...",
            "🔐 正在尝试暴力破解...",
            "📊 正在生成安全报告...",
            "✅ 安全测试即将完成..."
        ]
        
        if self.security_progress_step < len(progress_messages):
            message = progress_messages[self.security_progress_step - 1]
            self.progress_bar.setFormat(message)
            print(f"🔒 安全测试进度: {message}")
        else:
            # 循环显示进度消息
            message = progress_messages[(self.security_progress_step - 1) % len(progress_messages)]
            self.progress_bar.setFormat(message)
            print(f"🔒 安全测试进度: {message}")
        
        # 更新进度条值
        progress_value = min(90, self.security_progress_step * 10)
        self.progress_bar.setValue(progress_value)
    
    def stop_security_progress_update(self):
        """停止安全测试进度更新"""
        if hasattr(self, 'security_progress_timer'):
            self.security_progress_timer.stop()
            self.security_progress_timer = None
    def _on_settings_accepted(self):
        """设置窗口点击确定后的处理（非模态时调用）"""
        try:
            self.agent.update_tts_config(self.config)
            print("✅ TTS配置已更新")
        except Exception as e:
            print(f"⚠️ TTS配置更新失败: {str(e)}")
        self.apply_transparency()
        self.reload_global_shortcuts()

    def open_settings(self):
        """打开设置窗口（独立窗口，任务栏单独显示）"""
        settings_dialog = SettingsDialog(self.config, None, self.update_transparency)
        settings_dialog.accepted.connect(self._on_settings_accepted)
        settings_dialog.setAttribute(Qt.WA_DeleteOnClose)
        settings_dialog.setWindowFlags(settings_dialog.windowFlags() | Qt.Window)
        self._settings_dialog = settings_dialog  # 保持引用，避免被回收
        settings_dialog.show()

    def open_memory_lake(self):
        """打开识底深湖窗口（独立窗口，任务栏单独显示）"""
        memory_dialog = MemoryLakeDialog(self.agent.memory_lake, None)
        memory_dialog.setAttribute(Qt.WA_DeleteOnClose)
        memory_dialog.setWindowFlags(memory_dialog.windowFlags() | Qt.Window)
        self._memory_lake_dialog = memory_dialog  # 保持引用，避免被回收
        memory_dialog.show()

    def open_mcp_tools(self):
        """打开MCP工具窗口（独立窗口，任务栏单独显示）"""
        mcp_dialog = MCPToolsDialog(self.agent.mcp_tools, None)
        mcp_dialog.setAttribute(Qt.WA_DeleteOnClose)
        mcp_dialog.setWindowFlags(mcp_dialog.windowFlags() | Qt.Window)
        self._mcp_dialog = mcp_dialog  # 保持引用，避免被回收
        mcp_dialog.show()

    def sync_time(self):
        """同步网络时间"""
        try:
            import requests
            response = requests.get('http://worldtimeapi.org/api/timezone/Asia/Shanghai', timeout=5)
            data = response.json()
            current_time = datetime.datetime.fromisoformat(data['datetime'].replace('Z', '+00:00'))
            time_str = current_time.strftime("%H:%M:%S")
            self.ai_time.setText(time_str)
        except:
            # 如果网络时间同步失败，使用本地时间
            self.ai_time.setText(datetime.datetime.now().strftime("%H:%M:%S"))

    def update_status(self):
        """更新状态"""
        # 更新记忆系统状态
        mem_status = "开发者模式" if getattr(self.agent, 'developer_mode', False) else "正常"
        self.ai_memory.setText(mem_status)

        # 更新时间（每5秒同步一次网络时间）
        if hasattr(self, 'time_sync_counter'):
            self.time_sync_counter += 1
        else:
            self.time_sync_counter = 0
        
        if self.time_sync_counter % 5 == 0:  # 每5次更新同步一次网络时间
            self.sync_time()
        else:
            # 使用本地时间更新
            current_time = datetime.datetime.now()
            time_str = current_time.strftime("%H:%M:%S")
            self.ai_time.setText(time_str)

        # 更新状态栏
        time_str = self.ai_time.text()
        self.statusBar().showMessage(
            f"就绪 | 模型: {self.config.get('selected_model', 'deepseek-reasoner')} | 记忆系统: {mem_status} | {time_str}")

    def _voice_shortcut_hook(self, event):
        """键盘 hook：语音快捷键按下/松开时等同于麦克风按钮（需在主线程执行 UI）"""
        if not getattr(self, '_voice_shortcut_key', None):
            return
        try:
            name = getattr(event, 'name', None) or getattr(event, 'scan_code', '')
            name_lower = str(name).lower()
            event_type = getattr(event, 'event_type', 'down')
            if name_lower != self._voice_shortcut_key:
                return
            if event_type == 'down':
                mods = getattr(self, '_voice_shortcut_modifiers', [])
                if mods and not all(keyboard.is_pressed(m) for m in mods):
                    return
                QTimer.singleShot(0, self._on_voice_pressed)
            else:
                QTimer.singleShot(0, self._on_voice_released)
        except Exception:
            pass

    def setup_global_shortcuts(self):
        """设置全局快捷键（使用 keyboard 库）"""
        if not KEYBOARD_AVAILABLE:
            print("⚠️ keyboard 库不可用，全局快捷键功能已禁用")
            return

        # 移除之前的语音快捷键 hook（若存在）
        if getattr(self, '_voice_hook_callback', None) is not None:
            try:
                keyboard.unhook(self._voice_hook_callback)
            except Exception:
                pass
            self._voice_hook_callback = None
        self._voice_shortcut_key = None
        self._voice_shortcut_modifiers = []

        try:
            # 设置窗口呼出快捷键
            show_window_key = self.config.get("show_window_key_sequence", "ctrl+shift+l")
            keyboard.add_hotkey(show_window_key, self.show_and_activate_window)
            print(f"✅ 窗口呼出快捷键已设置: {show_window_key}")
            
            # 设置发送消息的全局快捷键（可选，因为输入框已经有快捷键了）
            send_key_sequence = self.config.get("send_key_sequence", "ctrl+enter")
            if send_key_sequence and send_key_sequence != "enter":
                try:
                    keyboard.add_hotkey(send_key_sequence, self.send_message_global)
                    print(f"✅ 发送消息全局快捷键已设置: {send_key_sequence}")
                except Exception as e:
                    print(f"⚠️ 设置发送消息全局快捷键失败: {str(e)}")

            # 语音输入快捷键（按住说话，松开结束）
            voice_seq = (self.config.get("voice_input_key_sequence") or "").strip().lower()
            if voice_seq:
                parts = [p.strip() for p in voice_seq.split("+") if p.strip()]
                if parts:
                    self._voice_shortcut_key = parts[-1]
                    self._voice_shortcut_modifiers = parts[:-1]
                    self._voice_hook_callback = self._voice_shortcut_hook
                    keyboard.hook(self._voice_hook_callback)
                    print(f"✅ 语音输入快捷键已设置: {voice_seq}（按住说话，松开结束）")
        except Exception as e:
            print(f"⚠️ 设置全局快捷键失败: {str(e)}")
    
    def show_and_activate_window(self):
        """显示并激活窗口（用于快捷键呼出）"""
        # keyboard 库的回调在后台线程中执行，需要使用 QTimer 将操作调度到主线程
        try:
            # 使用 QTimer.singleShot(0, ...) 将操作排队到主线程的事件循环
            QTimer.singleShot(0, self._show_and_activate_window_main_thread)
        except Exception as e:
            print(f"⚠️ 调度窗口呼出操作失败: {str(e)}")
    
    def _show_and_activate_window_main_thread(self):
        """在主线程中显示并激活窗口"""
        try:
            if self.isMinimized():
                # 如果窗口最小化，恢复并显示
                self.showNormal()
            elif not self.isVisible():
                # 如果窗口隐藏，显示
                self.show()
            
            # 激活窗口并置于最前
            self.activateWindow()
            self.raise_()
            
            # 将焦点设置到输入框
            if hasattr(self, 'input_edit'):
                self.input_edit.setFocus()
            
            print("✅ 窗口已呼出并激活")
        except Exception as e:
            print(f"⚠️ 呼出窗口失败: {str(e)}")
    
    def send_message_global(self):
        """全局快捷键发送消息（仅在窗口可见时有效）"""
        # keyboard 库的回调在后台线程中执行，需要使用 QTimer 将操作调度到主线程
        try:
            # 使用 QTimer.singleShot(0, ...) 将操作排队到主线程的事件循环
            QTimer.singleShot(0, self._send_message_global_main_thread)
        except Exception as e:
            print(f"⚠️ 调度全局发送消息操作失败: {str(e)}")
    
    def _send_message_global_main_thread(self):
        """在主线程中发送消息"""
        try:
            if self.isVisible() and not self.isMinimized():
                # 只有当窗口可见且未最小化时才发送消息
                self.send_message()
        except Exception as e:
            print(f"⚠️ 全局快捷键发送消息失败: {str(e)}")
    
    def reload_global_shortcuts(self):
        """重新加载全局快捷键（用于设置更改后）"""
        if not KEYBOARD_AVAILABLE:
            return
        try:
            # 先移除语音 hook（unhook_all_hotkeys 不会移除 hook）
            if getattr(self, '_voice_hook_callback', None) is not None:
                try:
                    keyboard.unhook(self._voice_hook_callback)
                except Exception:
                    pass
                self._voice_hook_callback = None
            # 清除所有已注册的热键
            keyboard.unhook_all_hotkeys()
            # 重新设置
            self.setup_global_shortcuts()
            print("✅ 全局快捷键已重新加载")
        except Exception as e:
            print(f"⚠️ 重新加载全局快捷键失败: {str(e)}")

    def closeEvent(self, event):
        """程序退出时的处理"""
        try:
            # 清理全局快捷键与语音 hook
            if KEYBOARD_AVAILABLE:
                try:
                    if getattr(self, '_voice_hook_callback', None) is not None:
                        keyboard.unhook(self._voice_hook_callback)
                        self._voice_hook_callback = None
                    keyboard.unhook_all_hotkeys()
                    print("✅ 全局快捷键已清理")
                except Exception as e:
                    print(f"⚠️ 清理全局快捷键失败: {str(e)}")
            
            # 静默保存未保存的会话记录到识底深湖
            self.save_unsaved_conversations_silent()
            
            # 清理AI Agent资源
            self.cleanup_ai_agent_resources()
            
            # 显示退出消息
            self.statusBar().showMessage("正在保存会话记录...")
            
            # 接受关闭事件
            event.accept()
            
        except Exception as e:
            # 静默处理异常，避免终端输出
            event.accept()

    def save_unsaved_conversations_silent(self):
        """静默保存未保存的会话记录到识底深湖（无终端输出）"""
        try:
            # 检查开发者模式，如果开启则不保存
            if getattr(self.agent, 'developer_mode', False):
                return
            
            # 获取当前会话中的对话记录
            session_conversations = getattr(self.agent, 'session_conversations', [])
            
            # 🔥 修复：同时检查 memory_lake.current_conversation 中未保存的对话
            memory_conversations = getattr(self.agent.memory_lake, 'current_conversation', [])
            
            # 合并两个来源的对话记录
            all_conversations = []
            
            # 从 session_conversations 添加
            for conv in session_conversations:
                if not conv.get('saved', False):
                    all_conversations.append({
                        'user_input': conv.get('user_input', ''),
                        'ai_response': conv.get('ai_response', ''),
                        'source': 'session'
                    })
            
            # 从 memory_lake.current_conversation 添加（可能不在 session_conversations 中）
            for conv in memory_conversations:
                user_input = conv.get('user_input', '')
                ai_response = conv.get('ai_response', '')
                # 检查是否已经在 session_conversations 中
                found_in_session = False
                for session_conv in session_conversations:
                    if (session_conv.get('user_input') == user_input and 
                        session_conv.get('ai_response') == ai_response):
                        found_in_session = True
                        break
                if not found_in_session:
                    all_conversations.append({
                        'user_input': user_input,
                        'ai_response': ai_response,
                        'source': 'memory_lake'
                    })
            
            if not all_conversations:
                # 如果所有对话都已保存，但 memory_lake.current_conversation 还有内容，直接保存
                if memory_conversations:
                    topic = self.agent.memory_lake.summarize_and_save_topic(force_save=True)
                    if topic:
                        print(f"💾 退出时保存了 {len(memory_conversations)} 条对话到识底深湖，主题: {topic}")
                return
            
            # 🚀 修复：遍历未保存的对话记录，将它们添加到记忆系统中
            for conv in all_conversations:
                user_input = conv.get('user_input', '')
                ai_response = conv.get('ai_response', '')
                
                if user_input and ai_response:
                    # 如果已经在 memory_lake.current_conversation 中，跳过添加
                    already_in_memory = False
                    for mem_conv in memory_conversations:
                        if (mem_conv.get('user_input') == user_input and 
                            mem_conv.get('ai_response') == ai_response):
                            already_in_memory = True
                            break
                    
                    if not already_in_memory:
                        # 添加到记忆系统的当前会话中
                        self.agent.memory_lake.add_conversation(user_input, ai_response, self.agent.developer_mode, self.agent._mark_conversation_as_saved)
            
            # 🚀 修复：强制保存当前会话（即使不足3条）
            if self.agent.memory_lake.current_conversation:
                topic = self.agent.memory_lake.summarize_and_save_topic(force_save=True)
                if topic:
                    # 🚀 修复：在成功保存后，标记所有对话为已保存
                    for conv in all_conversations:
                        if conv.get('source') == 'session':
                            # 在 session_conversations 中找到并标记
                            for session_conv in session_conversations:
                                if (session_conv.get('user_input') == conv.get('user_input') and 
                                    session_conv.get('ai_response') == conv.get('ai_response')):
                                    session_conv['saved'] = True
                                    break
                else:
                    # 🚀 修复：即使保存失败，也标记为已保存，避免重复尝试
                    for conv in all_conversations:
                        if conv.get('source') == 'session':
                            for session_conv in session_conversations:
                                if (session_conv.get('user_input') == conv.get('user_input') and 
                                    session_conv.get('ai_response') == conv.get('ai_response')):
                                    session_conv['saved'] = True
                                    break
            
            # 🚀 修复：不清空session_conversations，只标记为已保存
            # 这样可以避免重复保存，同时保留对话历史
            
        except Exception as e:
            # 静默处理异常，避免终端输出
            pass
    
    def cleanup_ai_agent_resources(self):
        """清理AI Agent相关资源"""
        try:
            # 清理TTS资源
            if hasattr(self.agent, 'cleanup_tts'):
                self.agent.cleanup_tts()
            
            # 清理Playwright资源
            if hasattr(self.agent, 'playwright_tool'):
                try:
                    self.agent.playwright_tool.close_sync()
                except:
                    pass
            
            # 清理记忆系统资源
            if hasattr(self.agent, 'memory_lake'):
                # 确保记忆系统正确关闭
                pass
            
            # 触发全局资源清理
            from async_resource_manager import get_resource_manager
            get_resource_manager().cleanup_all()
                
        except Exception:
            # 静默处理所有异常
            pass
    
    def check_first_run_and_introduce(self):
        """检查是否是第一次运行，如果是则进行自我介绍；检查迁移状态"""
        try:
            # 优先检查是否有待迁移的记忆数据
            migration_status = self.agent.memory_lake.get_migration_status()
            if migration_status:
                old_count = migration_status["old_memory_count"]
                current_count = migration_status["current_memory_count"]
                
                migration_message = f"指挥官，我检测到旧版本的记忆文件，其中包含 {old_count} 条历史记忆。"
                migration_message += f"当前系统中有 {current_count} 条记忆。\n\n"
                migration_message += "是否将旧记忆迁移到新的智能回忆系统中？"
                migration_message += "迁移后您将获得更精准的记忆检索和四维度智能回忆功能。\n\n"
                migration_message += "请回答'是'或'否'。"
                
                # 主动发送迁移询问消息
                self.add_message("露尼西亚", migration_message)
                return
            
            # 检查记忆系统中的记忆条数
            memory_stats = self.agent.memory_lake.get_memory_stats()
            total_topics = memory_stats.get("total_topics", 0)
            
            # 如果记忆条数为0，说明是第一次运行
            if total_topics == 0:
                # 生成自我介绍内容
                introduction = self.generate_introduction()
                
                # 将自我介绍添加到聊天历史
                self.add_message("露尼西亚", introduction)
                
                # 将自我介绍添加到AI代理的会话记录中，标记为系统消息
                self.agent._add_session_conversation("系统", introduction)
                # 🎯 立即标记系统消息为已保存，避免退出时重复保存
                self.agent._mark_conversation_as_saved("系统", introduction)
                
                # 设置首次介绍标记
                self.first_introduction_given = True
                self.waiting_for_first_response = True
                
        except Exception as e:
            print(f"⚠️ 启动检查失败: {e}")
    
    def generate_introduction(self):
        """生成露尼西亚的自我介绍"""
        current_time = datetime.datetime.now()
        time_str = current_time.strftime("%H:%M")
        
        introduction = f"""（轻轻整理了一下衣服）指挥官，您好！我是露尼西亚，威廉的姐姐。

很高兴见到您！作为您的AI助手，我具备以下能力：
• 智能对话和问题解答
• 天气查询和实时信息
• 音乐推荐和文件管理
• 编程代码生成和帮助
• 多语言交流和翻译
• 记忆系统"识底深湖"

现在时间是 {time_str}，我已经准备好为您服务了。请告诉我您需要什么帮助吧！

（对了，如果您想了解我的更多功能，可以直接问我"你能做什么"哦~）"""
        
        return introduction