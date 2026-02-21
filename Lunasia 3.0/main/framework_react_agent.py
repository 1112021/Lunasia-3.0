#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
框架ReAct Agent - 轻量级任务规划协调器
只负责制定执行框架，具体操作由主Agent完成
"""

import json
from typing import Dict, Any, List, Optional

class FrameworkReActAgent:
    """框架ReAct Agent - 任务分解和协调"""
    
    def __init__(self, base_agent, intent_model: str = "deepseek-chat"):
        """
        初始化框架Agent
        
        Args:
            base_agent: 基础AIAgent实例
            intent_model: 意图识别使用的模型
        """
        self.base_agent = base_agent
        self.intent_model = intent_model
        self.max_steps = 15  # 最大步数
        self.current_framework = []  # 当前框架
        self.completed_steps = []  # 已完成的步骤
        
    def _ai_identify_file_creation_intent(self, user_input: str) -> tuple:
        """
        使用AI快速识别用户是否想要创建/保存文件，并识别保存内容类型
        
        Args:
            user_input: 用户输入
            
        Returns:
            (bool, str): (是否文件创建请求, 内容类型:code/music/travel/general)
        """
        try:
            import openai
            
            # 使用轻量级chat模型
            model = "deepseek-chat"
            api_key = self.base_agent.config.get("deepseek_key", "")
            
            if not api_key:
                print("⚠️ 无API密钥，无法识别文件创建意图，继续框架流程")
                return (False, "")  # 返回False让框架继续处理
            
            # 🔥 获取最近对话上下文，判断要保存什么内容
            recent_context = ""
            if self.base_agent.session_conversations:
                for conv in self.base_agent.session_conversations[-2:]:
                    user_msg = conv.get('user_input', '')
                    ai_resp = conv.get('ai_response', '')
                    has_code = "```" in ai_resp
                    has_music = any(kw in ai_resp for kw in ["推荐", "音乐", "歌曲", "歌单"])
                    recent_context += f"用户: {user_msg}\nAI回复特征: [包含代码={has_code}, 包含音乐={has_music}]\n\n"
            
            prompt = f"""判断用户是否想要创建或保存文件，并识别要保存的内容类型。

用户输入：{user_input}

最近对话上下文：
{recent_context}

判断标准：
1. **是否是文件创建请求**：
   - 明确的保存操作："保存"、"创建文件"、"写入文件"、"保存到" → YES
   - 只请求内容不说保存："推荐音乐"、"写代码"（不说保存） → NO

2. **识别保存内容类型**（如果是保存请求）：
   - 用户明确指出："保存代码" → content_type="code"
   - 用户明确指出："保存歌单"/"保存音乐" → content_type="music"
   - 用户没明确指出，默认使用**最近的**内容：
     * 上文AI回复包含音乐 → content_type="music"
     * 上文AI回复包含代码 → content_type="code"
     * 否则 → content_type="general"

返回JSON：
{{
    "is_file_creation": true/false,
    "content_type": "code/music/travel/general"
}}

只返回JSON，不要其他内容。"""

            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            )
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是文件创建意图识别助手。只返回JSON。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1,
                timeout=15
            )
            
            result = response.choices[0].message.content.strip()
            print(f"🔍 [文件创建意图识别] AI返回: {result}")
            
            # 解析JSON
            import json
            result = result.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.endswith('```'):
                result = result[:-3]
            result = result.strip()
            
            result_dict = json.loads(result)
            is_file_creation = result_dict.get("is_file_creation", False)
            content_type = result_dict.get("content_type", "general")
            
            print(f"🔍 [文件创建意图识别] 判断: 创建={is_file_creation}, 类型={content_type}")
            return (is_file_creation, content_type)
            
        except Exception as e:
            print(f"⚠️ AI文件创建意图识别失败: {e}，返回False继续框架流程")
            return (False, "")
    
    def _fast_path_open_website(self, user_input: str) -> Optional[List[Dict[str, Any]]]:
        """检测是否属于纯"打开网站/网页"的简单请求，返回最小执行框架。
        触发条件示例：
        - 打开哔哩哔哩 / 打开bilibili / 打开 bilibili.com
        - 去知乎 / 打开百度
        - open youtube / go to github

        若检测到简单导航意图，则仅规划：
        1) get_url_from_website_map（提取URL）
        2) call_playwright_react（执行打开，仅传入原始user_input防止额外动作）
        3) pass_to_main_agent（总结）
        """
        text = user_input.strip().lower()
        
        # 关键词启发式（尽量保守，减少误判）
        trigger_keywords = ["打开", "open", "go to", "进入", "去", "上", "访问"]
        site_indicators = [".com", ".cn", ".net", ".org", "bilibili", "哔哩", "b站", "baidu", "google", "知乎", "zhihu", "github", "youtube", "优酷", "youku"]

        is_simple = any(k in user_input for k in trigger_keywords) and any(s in user_input for s in site_indicators)
        # 明确排除包含搜索、登录、点击、播放量等操作词的复杂场景
        complex_indicators = ["搜索", "search", "登录", "login", "点击", "click", "播放量", "highest", "排序", "sort", "下载", "download"]
        if any(c in user_input for c in complex_indicators):
            return None

        # 如果是纯域名或带http的也视为简单
        if ("http://" in text) or ("https://" in text) or text.startswith("www."):
            is_simple = True

        if not is_simple:
            return None

        # 使用AI提取网站名称（不是整个用户输入）
        # AI会判断是否是安全测试任务，如果是会返回None
        site_name = self.base_agent._ai_identify_website_intent(user_input)
        
        if not site_name:
            print(f"⚠️ 无法从'{user_input}'中提取网站名称（可能是安全测试任务，将使用HexStrike工具）")
            return None
        
        print(f"✅ [网站名称提取] 从'{user_input}' 提取到 '{site_name}'")

        return [
            {"description": f"获取『{site_name}』的URL", "action": "get_url_from_website_map", "params": {"website_name": site_name}},
            {"description": "在浏览器中打开该网站", "action": "call_playwright_react", "params": {"url": "从上一步获取的URL"}},
            {"description": "总结并回复用户", "action": "pass_to_main_agent", "params": {}}
        ]

    def _check_file_context_needed(self, user_input: str) -> bool:
        """
        检查用户问题是否需要结合文件上下文
        
        Args:
            user_input: 用户输入
            
        Returns:
            是否需要读取文件内容
        """
        try:
            # 检查是否有最近分析的文件
            if not self.base_agent.recent_file_analysis:
                print(f"📂 [文件上下文检查] 未检测到最近分析的文件")
                return False
            
            file_info = self.base_agent.recent_file_analysis
            print(f"📂 [文件上下文检查] 检测到最近分析的文件: {file_info['file_name']}")
            print(f"🤔 [文件上下文检查] 判断问题是否与文件相关...")
            
            # 使用AI判断问题是否与文件相关
            import openai
            
            api_key = self.base_agent.config.get("deepseek_key", "")
            if not api_key:
                print("⚠️ [文件上下文检查] 无API密钥，跳过AI判断")
                return False
            
            judge_prompt = f"""你刚刚分析了一个文件：{file_info['file_name']} ({file_info['file_type']})

现在用户提出了一个问题："{user_input}"

请判断这个问题是否与刚才分析的文件相关。

判断标准：
1. 如果问题明确提到"文件"、"代码"、"刚才"、"这个"等指代刚分析的文件
2. 如果问题询问代码结构、数量统计（如循环数、函数数）
3. 如果问题是对文件内容的追问或延伸讨论
4. 如果问题很简短且像是对上一次分析的追问（如"里边用了几个循环"、"这个文件的功能是什么"）

请只回答 "YES" 或 "NO"，不要有其他内容。"""
            
            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            )
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是文件上下文判断助手。只回答YES或NO。"},
                    {"role": "user", "content": judge_prompt}
                ],
                max_tokens=10,
                temperature=0.1,
                timeout=10
            )
            
            judge_result = response.choices[0].message.content.strip().upper()
            is_related = "YES" in judge_result
            
            if is_related:
                print(f"✅ [文件上下文检查] AI判断：问题与文件 {file_info['file_name']} 相关，需要读取文件内容")
            else:
                print(f"❌ [文件上下文检查] AI判断：问题与文件无关，使用常规处理流程")
            
            return is_related
            
        except Exception as e:
            print(f"⚠️ [文件上下文检查] 判断失败: {e}")
            return False
    
    def _check_image_context_needed(self, user_input: str) -> bool:
        """
        检查用户问题是否需要结合图片上下文
        
        Args:
            user_input: 用户输入
            
        Returns:
            是否需要读取图片内容
        """
        try:
            # 检查是否有最近分析的图片
            if not self.base_agent.recent_image_analysis:
                print(f"🖼️ [图片上下文检查] 未检测到最近分析的图片")
                return False
            
            image_info = self.base_agent.recent_image_analysis
            print(f"🖼️ [图片上下文检查] 检测到最近分析的图片: {image_info['image_name']}")
            print(f"🤔 [图片上下文检查] 判断问题是否与图片相关...")
            
            # 使用AI判断问题是否与图片相关
            import openai
            
            api_key = self.base_agent.config.get("deepseek_key", "")
            if not api_key:
                print("⚠️ [图片上下文检查] 无API密钥，跳过AI判断")
                return False
            
            judge_prompt = f"""你刚刚分析了一张图片：{image_info['image_name']}

现在用户提出了一个问题："{user_input}"

请判断这个问题是否与刚才分析的图片相关。

判断标准：
1. 如果问题明确提到"图片"、"照片"、"图像"、"刚才"、"这个"等指代刚分析的图片
2. 如果问题询问图片中的内容、文字、物体、场景等
3. 如果问题是对图片内容的追问或延伸讨论
4. 如果问题很简短且像是对上一次分析的追问（如"图片里有什么"、"这张图片的内容是什么"）

请只回答 "YES" 或 "NO"，不要有其他内容。"""
            
            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            )
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是图片上下文判断助手。只回答YES或NO。"},
                    {"role": "user", "content": judge_prompt}
                ],
                max_tokens=10,
                temperature=0.1,
                timeout=10
            )
            
            judge_result = response.choices[0].message.content.strip().upper()
            is_related = "YES" in judge_result
            
            if is_related:
                print(f"✅ [图片上下文检查] AI判断：问题与图片 {image_info['image_name']} 相关，需要读取图片内容")
            else:
                print(f"❌ [图片上下文检查] AI判断：问题与图片无关，使用常规处理流程")
            
            return is_related
            
        except Exception as e:
            print(f"⚠️ [图片上下文检查] 判断失败: {e}")
            return False

    def _check_video_context_needed(self, user_input: str) -> bool:
        """
        检查用户问题是否需要结合视频上下文
        
        Args:
            user_input: 用户输入
            
        Returns:
            是否需要读取视频内容
        """
        try:
            # 检查是否有最近分析的视频
            if not self.base_agent.recent_video_analysis:
                print(f"🎬 [视频上下文检查] 未检测到最近分析的视频")
                return False
            
            video_info = self.base_agent.recent_video_analysis
            print(f"🎬 [视频上下文检查] 检测到最近分析的视频: {video_info['video_name']}")
            print(f"🤔 [视频上下文检查] 判断问题是否与视频相关...")
            
            # 使用AI判断问题是否与视频相关
            import openai
            
            api_key = self.base_agent.config.get("deepseek_key", "")
            if not api_key:
                print("⚠️ [视频上下文检查] 无API密钥，跳过AI判断")
                return False
            
            judge_prompt = f"""你刚刚分析了一个视频：{video_info['video_name']}

现在用户提出了一个问题："{user_input}"

请判断这个问题是否与刚才分析的视频相关。

判断标准：
1. 如果问题明确提到"视频"、"刚才"、"这个"等指代刚分析的视频
2. 如果问题询问视频中的内容、文字、物体、场景、动作等
3. 如果问题是对视频内容的追问或延伸讨论
4. 如果问题很简短且像是对上一次分析的追问（如"视频里有什么"、"这个视频的内容是什么"）

请只回答 "YES" 或 "NO"，不要有其他内容。"""
            
            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            )
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是视频上下文判断助手。只回答YES或NO。"},
                    {"role": "user", "content": judge_prompt}
                ],
                max_tokens=10,
                temperature=0.1,
                timeout=10
            )
            
            judge_result = response.choices[0].message.content.strip().upper()
            is_related = "YES" in judge_result
            
            if is_related:
                print(f"✅ [视频上下文检查] AI判断：问题与视频 {video_info['video_name']} 相关，需要读取视频内容")
            else:
                print(f"❌ [视频上下文检查] AI判断：问题与视频无关，使用常规处理流程")
            
            return is_related
            
        except Exception as e:
            print(f"⚠️ [视频上下文检查] 判断失败: {e}")
            return False

    def process_command(self, user_input: str) -> str:
        """
        使用框架ReAct模式处理命令
        
        工作流程：
        1. 制定执行框架
        2. 逐步执行框架
        3. 动态调整框架（如果需要）
        4. 返回最终结果
        """
        print("\n" + "="*60)
        print("🧠 [框架ReAct] 启动任务规划引擎")
        print("="*60)
        
        # 0. 使用AI识别文件创建意图和内容类型
        is_file_creation, content_type = self._ai_identify_file_creation_intent(user_input)
        if is_file_creation:
            print(f"ℹ️ AI识别为文件创建请求（内容类型: {content_type}），直接交回主Agent处理")
            # 将识别的内容类型传递给主Agent
            self.base_agent.file_save_content_type = content_type
            return self.base_agent.process_command(user_input, skip_framework=True)

        # 🔥 新增：检查是否需要结合文件上下文
        needs_file_context = self._check_file_context_needed(user_input)
        
        # 🔥 新增：检查是否需要结合图片上下文
        needs_image_context = self._check_image_context_needed(user_input)
        
        # 🔥 新增：检查是否需要结合视频上下文
        needs_video_context = self._check_video_context_needed(user_input)

        # 🔥 如果检测到需要图片上下文，直接创建图片分析框架，跳过其他规划
        if needs_image_context:
            print("🖼️ [图片上下文] 检测到需要图片上下文，直接创建图片分析框架（跳过其他规划）")
            framework = [
                {
                    "description": "使用Qwen3VL-Plus模型分析最近上传的图片并直接返回结果",
                    "action": "analyze_image",
                    "params": {
                        "user_question": user_input,
                        "direct_return": True  # 标记直接返回，不传递给主agent
                    }
                }
            ]
        # 🔥 如果检测到需要视频上下文，直接创建视频分析框架，跳过其他规划
        elif needs_video_context:
            print("🎬 [视频上下文] 检测到需要视频上下文，直接创建视频分析框架（跳过其他规划）")
            framework = [
                {
                    "description": "使用Qwen3VL-Plus模型分析最近上传的视频并直接返回结果",
                    "action": "analyze_video",
                    "params": {
                        "user_question": user_input,
                        "direct_return": True  # 标记直接返回，不传递给主agent
                    }
                }
            ]
        # 第一步：检测是否是安全测试任务，如果是，让HexStrike AI自己规划
        elif self._is_security_test_task(user_input):
            print("=" * 60)
            print("🔒 [安全测试任务检测] 检测到安全测试请求")
            print(f"📝 用户输入: {user_input}")
            print("🔒 [安全测试任务] 将使用HexStrike AI智能规划")
            print("=" * 60)
            framework = self._create_hexstrike_intelligence_framework(user_input)
            print(f"📋 [框架创建] 已创建HexStrike AI智能规划框架，共 {len(framework)} 步")
            for i, step in enumerate(framework, 1):
                print(f"  [{i}] {step.get('description', 'N/A')} (action: {step.get('action', 'N/A')})")
            print("=" * 60)
        # 第二步：针对简单"只打开网站"的需求，走快速通道，避免多余动作
        else:
            simple_framework = self._fast_path_open_website(user_input)
            if simple_framework:
                framework = simple_framework
            else:
                # 常规：调用规划模型制定执行框架
                framework = self._plan_framework(user_input)
        
        # 🔥 如果检测到需要文件上下文，即使框架为None也要创建包含analyze_file的框架
        if needs_file_context:
            print("📂 [文件上下文] 检测到需要文件上下文，创建文件分析框架")
            if not framework:
                # 如果框架为None，创建一个只包含文件分析和传递的简单框架
                framework = [
                    {
                        "description": "读取最近分析的文件内容",
                        "action": "analyze_file",
                        "params": {}
                    },
                    {
                        "description": "将文件内容传递给主Agent回答",
                        "action": "pass_to_main_agent",
                        "params": {}
                    }
                ]
            else:
                # 如果框架存在，在开头添加文件分析步骤
                print("📂 [文件上下文] 在框架开头添加文件分析步骤")
                framework = [
                    {
                        "description": "读取最近分析的文件内容",
                        "action": "analyze_file",
                        "params": {}
                    }
                ] + framework
        
        if not framework:
            print("❌ 无法制定执行框架，使用标准模式")
            return None
        
        self.current_framework = framework
        total_steps = len(framework)
        
        print(f"\n📋 [执行框架] 共 {total_steps} 步")
        for i, step in enumerate(framework, 1):
            print(f"  [{i}] {step.get('description', 'N/A')} (action: {step.get('action', 'None')})")
        print("")
        
        # 逐步执行框架
        collected_info = {}  # 收集的信息
        
        for step_idx, step in enumerate(framework, 1):
            print(f"\n{'='*60}")
            print(f"🎯 [第 {step_idx}/{total_steps} 步] {step['description']}")
            print(f"{'='*60}")
            
            # 执行这一步
            result = self._execute_step(step, user_input, collected_info)
            
            print(f"✅ [完成] {result[:200]}{'...' if len(result) > 200 else ''}")
            
            # 保存结果
            collected_info[f"step_{step_idx}"] = result
            self.completed_steps.append({
                "step": step_idx,
                "description": step['description'],
                "action": step.get('action', ''),  # 🔥 保存action字段，用于后续判断
                "params": step.get('params', {}),  # 🔥 保存params字段，用于检查direct_return等标记
                "result": result
            })
            
            # 检查是否需要调整框架
            # 🔒 如果HexStrike AI已经规划了攻击链，不再调整其规划步骤，但可以添加其他步骤
            if step_idx < total_steps:
                # 检查已完成步骤中是否有HexStrike AI规划或执行
                has_hexstrike_planning = any(
                    s.get("action") in ["use_hexstrike_intelligence", "execute_hexstrike_attack_chain"]
                    for s in self.completed_steps
                )
                
                if has_hexstrike_planning:
                    # HexStrike AI已经规划过，检查剩余步骤
                    remaining_actions = [s.get("action", "") for s in framework[step_idx:]]
                    print("=" * 60)
                    print("🔒 [框架调整检查] HexStrike AI已规划攻击链")
                    print(f"   已完成步骤: {[s.get('action') for s in self.completed_steps]}")
                    print(f"   剩余步骤: {remaining_actions}")
                    if "pass_to_main_agent" in remaining_actions:
                        # 剩余步骤已经包含传递步骤，不需要调整
                        print("🔒 [框架调整] 剩余步骤已包含传递，跳过框架调整")
                        print("=" * 60)
                    else:
                        print("🔒 [框架调整] 剩余步骤缺少传递步骤，将添加")
                        print("=" * 60)
                        # 只添加传递步骤，不调整HexStrike AI的规划
                        print("🔒 HexStrike AI已规划攻击链，仅添加传递步骤，不调整攻击规划")
                        framework = framework[:step_idx] + framework[step_idx:] + [
                            {
                                "description": "将HexStrike AI规划结果传递给主Agent",
                                "action": "pass_to_main_agent",
                                "params": {}
                            }
                        ]
                        total_steps = len(framework)
                else:
                    # 没有HexStrike AI规划，正常调整
                    should_adjust = self._should_adjust_framework(user_input, collected_info, framework[step_idx:], result)
                    if should_adjust:
                        print(f"\n🔄 [框架调整] 根据当前进展重新规划后续步骤...")
                        new_framework = self._adjust_framework(user_input, collected_info, framework[step_idx:], result)
                        if new_framework:
                            # 更新框架
                            framework = framework[:step_idx] + new_framework
                            total_steps = len(framework)
                            print(f"📋 [新框架] 更新为 {total_steps} 步")
                            for i, s in enumerate(framework[step_idx:], step_idx + 1):
                                print(f"  [{i}] {s['description']}")
        
        # 生成最终回答
        print(f"\n{'='*60}")
        print(f"✅ [框架执行完成] 共完成 {len(self.completed_steps)} 步")
        print(f"{'='*60}\n")
        
        # 🔥 检查最后一步是否是analyze_image且标记为direct_return，如果是则直接返回结果
        if self.completed_steps:
            last_step = self.completed_steps[-1]
            if last_step.get("action") == "analyze_image":
                last_params = last_step.get("params", {})
                if last_params.get("direct_return", False):
                    print("🖼️ [图片分析] 检测到direct_return标记，直接返回图片分析结果")
                    return last_step.get("result", "")
            # 🔥 检查最后一步是否是analyze_video且标记为direct_return，如果是则直接返回结果
            elif last_step.get("action") == "analyze_video":
                last_params = last_step.get("params", {})
                if last_params.get("direct_return", False):
                    print("🎬 [视频分析] 检测到direct_return标记，直接返回视频分析结果")
                    return last_step.get("result", "")
        
        final_answer = self._generate_final_answer(user_input, collected_info)
        return final_answer
    
    def _plan_framework(self, user_input: str) -> List[Dict[str, Any]]:
        """
        制定执行框架
        
        Args:
            user_input: 用户输入
            
        Returns:
            框架列表 [{"description": "步骤描述", "action": "action_type", "params": {...}}]
        """
        prompt = f"""你是一个任务规划专家，需要为用户的请求制定执行框架。

用户请求：{user_input}

请分析用户的请求，制定执行框架。

**可用的操作类型：**
1. get_weather - 获取天气信息（直接调用天气API）
2. get_location - 获取位置信息
3. search_web - 搜索网络信息
4. analyze_file - 分析最近上传的文件
5. analyze_image - 使用Qwen3VL-Plus模型分析最近上传的图片
6. analyze_video - 使用Qwen3VL-Plus模型分析最近上传的视频
7. open_application - 打开应用程序
7. get_url_from_website_map - 从网站管理或AI知识库获取网站URL
8. call_playwright_react - 调用Playwright ReAct Agent执行网页自动化
9. use_mcp_tool - 使用MCP工具
10. use_hexstrike_tool - 使用HexStrike电子战工具（通过Kali Linux桥接）
11. start_hexstrike_ai - 启动HexStrike AI服务器（如果未运行）
12. pass_to_main_agent - 将信息传递给主Agent（用于最终回答）

       **HexStrike AI电子战工具说明：**
       露尼西亚使用真实的HexStrike AI MCP服务器，提供150+安全工具和12+自主AI代理。
       
       **可用的HexStrike AI工具（通过use_mcp_tool调用hexstrike_*）：**
       - hexstrike_port_scan: 端口扫描（参数：target, ports, scan_type）
       - hexstrike_directory_scan: 目录扫描（参数：url, wordlist）
       - hexstrike_subdomain_enum: 子域名枚举（参数：domain）
       - hexstrike_web_vuln_scan: Web漏洞扫描（参数：url）
       - hexstrike_sql_injection: SQL注入测试（参数：url, data）
       - hexstrike_nuclei_scan: Nuclei漏洞扫描（参数：target, templates）
       - hexstrike_masscan: 快速端口扫描（参数：target, ports, rate）
       - hexstrike_wpscan: WordPress扫描（参数：url, username, wordlist）
       - hexstrike_hydra: 密码暴力破解（参数：target, service, username, wordlist）
       - hexstrike_john: 哈希破解-John（参数：hash_file, wordlist）
       - hexstrike_hashcat: 哈希破解-Hashcat（参数：hash_file, hash_type, wordlist）
       - hexstrike_wfuzz: Web模糊测试（参数：url, wordlist, parameter）
       - hexstrike_whatweb: Web技术识别（参数：url）
       - hexstrike_dnsrecon: DNS侦察（参数：domain）
       - hexstrike_fierce: DNS暴力扫描（参数：domain）
       - hexstrike_dig: DNS查询-dig（参数：domain, record_type）
       - hexstrike_nslookup: DNS查询-nslookup（参数：domain, record_type）
       - hexstrike_whois: 域名信息查询（参数：domain）
       - hexstrike_enum4linux: SMB枚举（参数：target）
       - hexstrike_smbclient: SMB客户端连接（参数：target, share, username, password）
       - hexstrike_crackmapexec: 网络渗透测试（参数：target, username, password）
       - hexstrike_responder: LLMNR/NBT-NS毒化（参数：interface）
       - hexstrike_tcpdump: 网络抓包（参数：interface, count, output_file）
       - hexstrike_netcat: 网络连接测试（参数：target, port）
       - hexstrike_curl: HTTP请求（参数：url, method, data, headers）
       - hexstrike_wget: 文件下载（参数：url, output_file）
       - hexstrike_searchsploit: Exploit-DB搜索（参数：keyword）
       - hexstrike_tool_status: 获取工具状态
       - kali_execute: 在Kali Linux中执行任意命令（参数：command）
       - 以及更多150+工具（动态注册）...
       
       **启动HexStrike AI服务器：**
       使用HexStrike工具前，如果服务器未运行，必须先使用start_hexstrike_ai操作启动服务器。
       例如：{{"description": "启动HexStrike AI服务器", "action": "start_hexstrike_ai", "params": {{}}}}

**重要：安全测试任务必须使用HexStrike AI工具**
当用户请求涉及安全测试、渗透测试、漏洞扫描、分析HTML源码找密码等任务时，必须使用HexStrike AI工具（hexstrike_*），而不是使用Playwright。

**使用场景：**
- 分析HTML源码找密码/隐藏信息 → 使用kali_execute执行curl/wget获取源码，或使用hexstrike_web_vuln_scan
- 安全测试、渗透测试、漏洞扫描 → 使用相应的hexstrike工具
- 端口扫描、目录扫描、子域名枚举 → 使用相应的hexstrike工具
- 复杂渗透测试、自动化攻击链 → 使用hexstrike工具（需要先启动服务器）
- 需要执行Kali命令 → 使用kali_execute

**使用场景示例：**
- "分析HTML源码找密码" → start_hexstrike_ai启动服务器 + use_mcp_tool调用kali_execute执行"curl URL"获取源码
- "扫描hackthissite.org的端口" → start_hexstrike_ai启动服务器 + use_mcp_tool调用hexstrike_port_scan
- "对URL进行SQL注入测试" → start_hexstrike_ai启动服务器 + use_mcp_tool调用hexstrike_sql_injection
- "扫描网站的目录" → start_hexstrike_ai启动服务器 + use_mcp_tool调用hexstrike_directory_scan
- "进行完整的渗透测试" → start_hexstrike_ai启动服务器 + use_mcp_tool调用多个hexstrike工具

**规划原则：**
1. **步数完全自由**：根据任务复杂度自主决定，可以是1步、3步、8步或任意数量
2. **工具选择智能**：
   - 简单对话 → pass_to_main_agent（1步即可）
   - 天气查询 → get_weather + pass_to_main_agent
   - **普通网页操作**（非安全测试，如浏览网页、填写表单等） → get_url_from_website_map + call_playwright_react + pass_to_main_agent
   - **安全测试/电子战任务**（如分析HTML源码找密码、漏洞扫描、渗透测试等） → start_hexstrike_ai启动服务器 + use_mcp_tool调用hexstrike_*工具 + pass_to_main_agent（必须使用HexStrike AI，不要用Playwright）
   - 文件追问 → analyze_file + pass_to_main_agent
   - 图片追问 → analyze_image + pass_to_main_agent
   - 视频追问 → analyze_video + pass_to_main_agent（如果是分段分析结果会自动传递给主agent整合）
   - 信息查询 → search_web + pass_to_main_agent（最多2步，避免重复搜索）
   - 复杂任务 → 多个工具组合，但避免重复相同类型的搜索
   - **代码生成类任务** → 直接返回null（让主Agent处理）
3. **最后一步必须是pass_to_main_agent**：将收集的信息传给主Agent生成回答
4. **避免重复**：不要规划多个相同类型的search_web步骤，一次搜索即可
5. **电子战工具使用（优先级高于Playwright）**：
   - 分析HTML源码/找密码 → use_mcp_tool调用kali_execute("curl URL")或hexstrike_web_vuln_scan
   - 端口扫描请求 → use_mcp_tool调用hexstrike_port_scan（参数：target, ports="1-1000", scan_type="connect"表示TCP扫描，无需sudo）
   - 目录扫描请求 → use_mcp_tool调用hexstrike_directory_scan
   - 子域名枚举请求 → use_mcp_tool调用hexstrike_subdomain_enum
   - Web漏洞扫描 → use_mcp_tool调用hexstrike_web_vuln_scan
   - SQL注入测试 → use_mcp_tool调用hexstrike_sql_injection
   - WordPress扫描 → use_mcp_tool调用hexstrike_wpscan
   - 密码破解 → use_mcp_tool调用hexstrike_hydra或hexstrike_john或hexstrike_hashcat
   - DNS侦察 → use_mcp_tool调用hexstrike_dnsrecon或hexstrike_fierce或hexstrike_dig
   - SMB枚举 → use_mcp_tool调用hexstrike_enum4linux或hexstrike_smbclient
   - 网络抓包 → use_mcp_tool调用hexstrike_tcpdump
   - Exploit搜索 → use_mcp_tool调用hexstrike_searchsploit

**特别注意 - 直接交给主Agent的任务类型：**
如果用户请求属于以下类型，请直接返回 null（表示不需要框架规划，交给主Agent处理）：
- **代码生成**：写代码、用Python写、用Java写、用C++写、生成代码、编写程序等
- **文件创建**：保存文件、创建文件、写入文件等（已在前置检查中处理）
- **纯AI对话**：不需要任何工具调用的简单对话
- **音乐/电影/书籍推荐**：推荐音乐、推荐电影、推荐书籍等（主Agent可以直接生成）
- **创意内容生成**：写诗、写故事、写文章等（主Agent的创作能力）

识别标准：
- 包含"写"、"写个"、"写一个"、"帮我写"、"生成代码"、"编写"等词
- 明确提到编程语言：Python、Java、C++、JavaScript、Go等
- 要求HelloWorld、计算器、游戏等代码示例
- **推荐类请求**："推荐音乐"、"推荐歌曲"、"推荐电影"、"推荐书籍"
- **创作类请求**："写首诗"、"写个故事"、"帮我想个文案"

示例（应返回null）：
- "帮我用Java写个helloworld" → null
- "用Python写一个计算器" → null  
- "写个Python爬虫" → null
- "生成一个C++程序" → null
- **"推荐几首音乐" → null**
- **"推荐一些好听的歌" → null**
- **"帮我推荐几本书" → null**

**安全测试任务示例：**
- "分析 https://www.hackthissite.org/missions/basic/1/ 的HTML源码，找出隐藏的密码" 
  → [{{"description": "启动HexStrike AI服务器", "action": "start_hexstrike_ai", "params": {{}}}}, {{"description": "使用kali_execute执行curl获取HTML源码", "action": "use_mcp_tool", "params": {{"tool_name": "kali_execute", "params": {{"command": "curl -s https://www.hackthissite.org/missions/basic/1/"}}}}}}, {{"description": "分析源码并传递给主Agent", "action": "pass_to_main_agent", "params": {{}}}}]

- "扫描hackthissite.org的端口"
  → [{{"description": "启动HexStrike AI服务器", "action": "start_hexstrike_ai", "params": {{}}}}, {{"description": "使用hexstrike_port_scan扫描端口", "action": "use_mcp_tool", "params": {{"tool_name": "hexstrike_port_scan", "params": {{"target": "hackthissite.org", "ports": "1-1000", "scan_type": "connect"}}}}}}, {{"description": "传递扫描结果", "action": "pass_to_main_agent", "params": {{}}}}]

- "进行完整的渗透测试"
  → [{{"description": "启动HexStrike AI服务器", "action": "start_hexstrike_ai", "params": {{}}}}, {{"description": "使用hexstrike_port_scan进行端口扫描", "action": "use_mcp_tool", "params": {{"tool_name": "hexstrike_port_scan", "params": {{"target": "target.com", "ports": "1-65535"}}}}}}, {{"description": "使用hexstrike_subdomain_enum进行子域名枚举", "action": "use_mcp_tool", "params": {{"tool_name": "hexstrike_subdomain_enum", "params": {{"domain": "target.com"}}}}}}, {{"description": "传递测试结果", "action": "pass_to_main_agent", "params": {{}}}}]

- "进行完整的渗透测试，使用HexStrike AI"
  → [{{"description": "启动HexStrike AI服务器", "action": "start_hexstrike_ai", "params": {{}}}}, {{"description": "使用HexStrike AI进行端口扫描", "action": "use_mcp_tool", "params": {{"tool_name": "hexstrike_ai_port_scan", "params": {{"target": "target.com", "ports": "1-65535"}}}}}}, {{"description": "使用HexStrike AI进行子域名枚举", "action": "use_mcp_tool", "params": {{"tool_name": "hexstrike_ai_subdomain_enum", "params": {{"domain": "target.com"}}}}}}, {{"description": "传递测试结果", "action": "pass_to_main_agent", "params": {{}}}}]

**返回格式要求（严格遵守）：**
返回一个JSON数组，每个元素必须包含：
- "description": 步骤描述
- "action": 操作类型（从上面10种操作中选择）
- "params": 参数对象（可为空{{}}）

⚠️ 注意：字段名必须是"action"，不是"operation"或其他！

用户问题：{user_input}

请规划执行框架（JSON数组格式，只返回JSON，不要有其他内容）：
"""
        
        # 直接调用OpenAI API（因为base_agent没有统一的_call_ai_api方法）
        try:
            import openai
            
            # 获取API密钥
            if "deepseek" in self.intent_model:
                api_key = self.base_agent.config.get("deepseek_key", "")
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com/v1"
                )
            else:
                api_key = self.base_agent.config.get("openai_key", "")
                client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model=self.intent_model,
                messages=[
                    {"role": "system", "content": "你是任务规划专家，擅长将复杂任务分解为清晰的执行步骤。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7,
                timeout=15
            )
            
            response = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ API调用失败: {e}")
            return None
        
        try:
            # 清理响应
            response = response.strip()
            
            # 检查AI是否返回null（表示应该交给主Agent处理）
            if response.lower() in ["null", "none", "空"]:
                print("ℹ️ AI规划模型建议直接交给主Agent处理")
                return None
            
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # 再次检查是否为null
            if response.lower() in ["null", "none", "空"]:
                print("ℹ️ AI规划模型建议直接交给主Agent处理")
                return None
            
            framework = json.loads(response)
            
            # 调试：打印解析后的框架
            print(f"🔍 [调试] AI规划的框架: {json.dumps(framework, ensure_ascii=False, indent=2)}")
            
            # 如果返回空数组，说明不需要框架
            if not framework or len(framework) == 0:
                return None
            
            return framework
            
        except json.JSONDecodeError as e:
            print(f"❌ 框架解析失败: {e}")
            print(f"原始响应: {response[:200]}")
            return None
    
    def _execute_step(self, step: Dict, user_input: str, collected_info: Dict) -> str:
        """
        执行框架中的一步
        
        Args:
            step: 步骤定义
            user_input: 原始用户输入
            collected_info: 已收集的信息
            
        Returns:
            执行结果
        """
        action = step.get("action")
        params = step.get("params", {})
        
        try:
            if action == "get_location":
                location = self.base_agent.location
                return f"位置：{location}"
            
            elif action == "get_url_from_website_map":
                # 从网站管理或AI知识库获取URL
                # 支持多种可能的参数名：name, website, website_name
                site_name = (
                    params.get("name") or 
                    params.get("website") or 
                    params.get("website_name") or 
                    ""
                )
                print(f"    🔍 查找网站URL: {site_name}")
                print(f"    🔍 params内容: {params}")

                # 🔥 优先检查：如果用户输入或site_name中已包含完整URL，直接提取返回
                import re
                # 检查用户输入
                url_pattern = r'https?://[^\s\u4e00-\u9fff]+'  # 匹配http(s)://开头到中文或空格前的URL
                url_match = re.search(url_pattern, user_input)
                if url_match:
                    extracted_url = url_match.group(0)
                    # 移除末尾可能的中文字符
                    extracted_url = re.sub(r'[\u4e00-\u9fff]+$', '', extracted_url)
                    print(f"    ✅ 从用户输入中直接提取URL: {extracted_url}")
                    return f"获取到URL: {extracted_url}"
                
                # 检查site_name参数
                url_match = re.search(url_pattern, site_name)
                if url_match:
                    extracted_url = url_match.group(0)
                    extracted_url = re.sub(r'[\u4e00-\u9fff]+$', '', extracted_url)
                    print(f"    ✅ 从site_name参数中直接提取URL: {extracted_url}")
                    return f"获取到URL: {extracted_url}"

                # 占位/泛化词过滤：避免将"相关社交媒体平台"等占位词当成真实网站
                placeholder_indicators = [
                    "相关社交媒体平台", "相关平台", "相关网站", "某平台", "某网站", "社交平台", "社交媒体平台"
                ]
                if any(ind in site_name for ind in placeholder_indicators):
                    return "❌ 未提供明确网站名称，已跳过获取URL"
                
                # 优先从网站管理中查找
                website_map = self.base_agent.website_map
                url = website_map.get(site_name)
                
                # 如果没有，尝试AI生成
                if not url:
                    print(f"    🤖 网站管理中未找到，尝试AI生成URL...")
                    url = self.base_agent._ai_generate_website_url(site_name)
                    if url:
                        print(f"    ✅ AI成功生成URL: {url}")
                
                if url:
                    return f"获取到URL: {url}"
                else:
                    return f"❌ 无法找到网站 {site_name} 的URL"
            
            elif action == "call_playwright_react":
                # 调用Playwright ReAct Agent执行网页自动化
                url = params.get("url", "")
                # 如果用户是一般信息查询，不需要打开浏览器，直接跳过
                intent_open_keywords = ["打开", "浏览器", "登录", "点击", "网页", "在\n浏览器", "在浏览器", "搜索并打开", "访问", "进入"]
                informational_keywords = ["是谁", "现状", "状态", "被封", "是否", "怎么", "简介", "情况", "了吗", "吗", "介绍", "详细"]
                if any(k in user_input for k in informational_keywords) and not any(k in user_input for k in intent_open_keywords):
                    return "ℹ️ 这是信息查询任务，无需打开网页；已基于搜索给出答案"
                
                print(f"    🔍 原始URL参数: {url}")
                print(f"    🔍 已收集信息: {list(collected_info.keys())}")
                
                # 🔍 智能URL提取（从params或collected_info）
                # 检测占位符：previous、步骤、获取、{{、}}等
                is_placeholder = (
                    not url or 
                    "previous" in url.lower() or
                    "步骤" in url or 
                    "获取" in url or
                    "{{" in url or
                    "}}" in url or
                    not url.startswith("http")
                )
                
                if is_placeholder:
                    # URL是占位符，从已收集信息中提取实际URL
                    print(f"    🔄 检测到占位符，从已收集信息中提取URL...")
                    for key, value in collected_info.items():
                        if "获取到URL:" in str(value):
                            url = value.split("获取到URL:")[1].strip()
                            print(f"    ✅ 从{key}中提取URL: {url}")
                            break
                
                if not url or not url.startswith("http"):
                    print(f"    ❌ 最终URL无效: {url}")
                    return "❌ 未找到有效的网站URL，无法执行"
                
                print(f"    🤖 调用网页打开功能: {url}")
                print(f"    📝 用户任务: {user_input}")
                
                # 直接调用主Agent的网页打开功能（明确传递user_input参数）
                result = self.base_agent._open_website_wrapper(
                    site_name=url,
                    website_map=None,
                    user_input=user_input
                )
                return result
            
            elif action == "get_weather":
                # 从已收集信息中获取位置
                location_info = collected_info.get("step_1", "")
                city = self.base_agent._extract_city_from_location(location_info)
                if not city:
                    city = self.base_agent._extract_city_from_location(self.base_agent.location)
                
                weather_source = self.base_agent.config.get("weather_source", "高德地图API")
                if weather_source == "高德地图API":
                    from amap_tool import AmapTool
                    amap_key = self.base_agent.config.get("amap_key", "")
                    weather = AmapTool.get_weather(city, amap_key)
                else:
                    heweather_key = self.base_agent.config.get("heweather_key", "")
                    weather = self.base_agent.tools["天气"](city, heweather_key)
                
                return f"天气：{weather}"
            
            elif action == "search_web":
                query = params.get("query", user_input)
                # 临时开启搜索
                original = self.base_agent.config.get("enable_web_search", False)
                print(f"🔍 [框架search_web] 保存原始值: enable_web_search = {original}")
                
                try:
                    self.base_agent.config["enable_web_search"] = True
                    print(f"🔍 [框架search_web] 临时开启搜索")
                    
                    # 仅执行搜索与注入，不重复触发内层回忆（避免与主Agent重复）
                    result = self.base_agent._generate_response_with_context(query, {}, skip_memory_recall=True)
                    
                    return result
                finally:
                    # 确保无论如何都会恢复原始值
                    self.base_agent.config["enable_web_search"] = original
                    print(f"🔍 [框架search_web] 恢复原始值: enable_web_search = {original}")
            
            elif action == "analyze_file":
                if self.base_agent.recent_file_analysis:
                    info = self.base_agent.recent_file_analysis
                    # 🔥 返回更详细的文件信息，包括内容摘要，方便主agent结合上下文回答
                    file_context = f"""文件信息：
- 文件名：{info['file_name']}
- 文件类型：{info['file_type']}
- 文件摘要：{info.get('summary', '')}
- 文件分析：{info.get('analysis', '')}
"""
                    # 如果是代码文件，添加统计信息
                    if 'CODE_' in info.get('file_type', ''):
                        metadata = info.get('metadata', {})
                        structure = metadata.get('structure', {})
                        metrics = metadata.get('metrics', {})
                        
                        if metrics:
                            file_context += f"\n代码统计：\n"
                            if_count = metrics.get('if_count', metrics.get('if_statements', 0))
                            for_count = metrics.get('for_count', metrics.get('for_loops', 0))
                            while_count = metrics.get('while_count', metrics.get('while_loops', 0))
                            total_loops = for_count + while_count
                            file_context += f"- if语句：{if_count} 个\n"
                            file_context += f"- for循环：{for_count} 个\n"
                            file_context += f"- while循环：{while_count} 个\n"
                            file_context += f"- 循环总数：{total_loops} 个\n"
                            file_context += f"- 总行数：{metrics.get('total_lines', 0)} 行\n"
                        
                        if structure:
                            if structure.get('classes'):
                                file_context += f"- 类定义：{len(structure['classes'])} 个\n"
                            if structure.get('functions'):
                                file_context += f"- 函数/方法：{len(structure['functions'])} 个\n"
                    
                    # 添加部分文件内容（如果不太长）
                    content = info.get('content', '')
                    if content and len(content) < 5000:
                        file_context += f"\n文件内容（部分）：\n{content[:5000]}"
                    elif content:
                        file_context += f"\n文件内容（前5000字符）：\n{content[:5000]}..."
                    
                    return file_context
                return "❌ 无文件上下文"
            
            elif action == "analyze_image":
                # 使用Qwen3VL-Plus模型分析图片
                if self.base_agent.recent_image_analysis:
                    image_info = self.base_agent.recent_image_analysis
                    user_question = params.get("user_question", "")
                    direct_return = params.get("direct_return", False)
                    
                    print(f"🖼️ [图片分析] 使用Qwen3VL-Plus模型分析图片: {image_info['image_name']}")
                    if direct_return:
                        print("🖼️ [图片分析] 标记为直接返回模式，将直接返回结果")
                    
                    # 调用process_image方法，传入用户问题
                    result = self.base_agent.process_image(image_info['image_path'], user_question)
                    
                    # 更新图片分析上下文
                    self.base_agent.recent_image_analysis['analysis'] = result
                    
                    # 如果标记为直接返回，直接返回结果（不添加前缀）
                    if direct_return:
                        return result
                    else:
                        return f"图片分析结果：\n{result}"
                return "❌ 无图片上下文"
            
            elif action == "analyze_video":
                # 使用Qwen3VL-Plus模型分析视频
                if self.base_agent.recent_video_analysis:
                    video_info = self.base_agent.recent_video_analysis
                    user_question = params.get("user_question", "")
                    direct_return = params.get("direct_return", False)
                    
                    print(f"🎬 [视频分析] 使用Qwen3VL-Plus模型分析视频: {video_info['video_name']}")
                    if direct_return:
                        print("🎬 [视频分析] 标记为直接返回模式，将直接返回结果")
                    
                    # 调用process_video方法，传入用户问题
                    result = self.base_agent.process_video(video_info['video_path'], user_question)
                    
                    # 更新视频分析上下文
                    self.base_agent.recent_video_analysis['analysis'] = result
                    
                    # 🔥 检查是否是分段分析结果，只有分段分析才需要主agent整合
                    is_segmented = video_info.get('is_segmented', False) or "[SEGMENTED_VIDEO_ANALYSIS]" in result
                    
                    if is_segmented:
                        print("🎬 [视频分析] 检测到分段分析结果，将传递给主agent整合")
                        # 分段分析结果需要主agent整合，不直接返回
                        direct_return = False
                        # 移除标记，保留内容
                        if "[SEGMENTED_VIDEO_ANALYSIS]\n" in result:
                            result = result.replace("[SEGMENTED_VIDEO_ANALYSIS]\n", "")
                    
                    # 如果标记为直接返回且不是分段分析，直接返回结果
                    if direct_return and not is_segmented:
                        return result
                    else:
                        return f"视频分析结果：\n{result}"
                return "❌ 无视频上下文"
            
            elif action == "open_application":
                # 兼容多种参数名：name, application_name, app, app_name
                app_name = (
                    params.get("name") or
                    params.get("application_name") or
                    params.get("app") or
                    params.get("app_name") or
                    ""
                )
                return self.base_agent._open_application(app_name)
            
            elif action == "open_website":
                site_name = params.get("name", "")
                return self.base_agent._open_website_wrapper(site_name, user_input)
            
            elif action == "use_mcp_tool":
                # 使用MCP工具（包括HexStrike工具）
                tool_name = params.get("tool_name", "")
                tool_params = params.get("params", {})
                
                if not tool_name:
                    return "❌ 未指定MCP工具名称"
                
                result = self.base_agent.mcp_tools.execute_mcp_command(tool_name, **tool_params)
                return result
            
            elif action == "use_hexstrike_tool":
                # 使用HexStrike电子战工具（通过MCP工具调用）
                tool_name = params.get("tool_name", "")
                tool_params = params.get("params", {})
                
                if not tool_name:
                    return "❌ 未指定HexStrike工具名称"
                
                # HexStrike工具通过MCP工具调用
                result = self.base_agent.mcp_tools.execute_mcp_command(tool_name, **tool_params)
                return result
            
            elif action == "use_hexstrike_intelligence":
                # 使用HexStrike AI智能规划（让HexStrike AI自己规划攻击链）
                intelligence_type = params.get("intelligence_type", "create-attack-chain")
                target = params.get("target", "")
                objective = params.get("objective", None)
                
                if not target:
                    return "❌ 未指定目标"
                
                print(f"    🧠 正在使用HexStrike AI智能规划（类型: {intelligence_type}）...")
                try:
                    mcp_server = self.base_agent.mcp_tools.server
                    
                    if not hasattr(mcp_server, 'hexstrike_mcp_client') or not mcp_server.hexstrike_mcp_client:
                        return "❌ HexStrike AI客户端未初始化，请先启动服务器"
                    
                    # 根据类型调用不同的智能端点
                    if intelligence_type == "analyze-target":
                        result = mcp_server.hexstrike_analyze_target(target, params.get("analysis_type", "comprehensive"))
                    elif intelligence_type == "smart-scan":
                        result = mcp_server.hexstrike_smart_scan(target, params.get("scan_type", "comprehensive"))
                    elif intelligence_type == "create-attack-chain":
                        result = mcp_server.hexstrike_create_attack_chain(target, objective)
                    elif intelligence_type == "comprehensive-assessment":
                        result = mcp_server.hexstrike_comprehensive_assessment(target)
                    else:
                        return f"❌ 未知的智能规划类型: {intelligence_type}"
                    
                    return result
                except Exception as e:
                    import traceback
                    return f"❌ HexStrike AI智能规划失败: {str(e)}\n{traceback.format_exc()[:200]}"
            
            elif action == "execute_hexstrike_attack_chain":
                # 执行HexStrike AI攻击链（规划并执行，返回执行报告）
                target = params.get("target", "")
                objective = params.get("objective", None)
                
                print("=" * 60)
                print("🎯 [HexStrike AI执行] 开始执行攻击链")
                print(f"   📍 目标: {target}")
                print(f"   📝 任务描述: {objective[:100] if objective else 'N/A'}...")
                print("=" * 60)
                
                if not target:
                    print("❌ [HexStrike AI执行] 未指定目标")
                    return "❌ 未指定目标"
                
                print(f"    🚀 [步骤1] 调用HexStrike AI的execute_attack_chain方法...")
                print(f"    📋 [步骤1] 该方法将：")
                print(f"        1. 调用create-attack-chain进行规划")
                print(f"        2. 根据规划结果执行攻击链")
                print(f"        3. 返回执行报告")
                try:
                    mcp_server = self.base_agent.mcp_tools.server
                    
                    if not hasattr(mcp_server, 'hexstrike_mcp_client') or not mcp_server.hexstrike_mcp_client:
                        return "❌ HexStrike AI客户端未初始化，请先启动服务器"
                    
                    # 执行攻击链（会自动规划并执行）
                    result = mcp_server.hexstrike_execute_attack_chain(target, objective)
                    return result
                except Exception as e:
                    import traceback
                    return f"❌ HexStrike AI执行攻击链失败: {str(e)}\n{traceback.format_exc()[:200]}"
            
            elif action == "start_hexstrike_ai":
                # 启动HexStrike AI服务器
                print("=" * 60)
                print("🚀 [HexStrike AI启动] 开始启动HexStrike AI服务器...")
                try:
                    # 通过MCP服务器访问HexStrike AI客户端
                    mcp_server = self.base_agent.mcp_tools.server
                    
                    if not hasattr(mcp_server, 'hexstrike_mcp_client'):
                        return "❌ HexStrike AI客户端未初始化，请在ai_agent_config.json中配置hexstrike_ai"
                    
                    # 检查是否已运行
                    if mcp_server.hexstrike_mcp_client:
                        if mcp_server.hexstrike_mcp_client.is_available():
                            return "✅ HexStrike AI服务器已在运行"
                        else:
                            # 尝试重新连接
                            mcp_server.hexstrike_mcp_client._ensure_server_running()
                            if mcp_server.hexstrike_mcp_client.is_available():
                                return "✅ HexStrike AI服务器已启动"
                            else:
                                return "❌ HexStrike AI服务器启动失败，请检查配置和服务器路径"
                    else:
                        # 重新初始化
                        mcp_server._init_hexstrike_ai()
                        if mcp_server.hexstrike_mcp_client and mcp_server.hexstrike_mcp_client.is_available():
                            return "✅ HexStrike AI服务器已启动并连接成功"
                        else:
                            return "❌ HexStrike AI未配置或启动失败，请在ai_agent_config.json中配置hexstrike_ai（enabled: true, server_path: 服务器脚本路径）"
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    return f"❌ 启动HexStrike AI服务器失败: {str(e)}\n详情: {error_detail}"
            
            elif action == "pass_to_main_agent":
                # 将结果交给主Agent生成最终回答：复用主Agent系统提示与流程
                print(f"    🔄 将框架执行结果传递给主Agent总结...")

                # 为避免重复联网搜索：临时关闭联网搜索，但保留之前已写入的 search_context
                original_search_flag = self.base_agent.config.get("enable_web_search", False)
                self.base_agent.config["enable_web_search"] = False
                try:
                    # 直接调用主Agent的对话处理流程，并显式跳过框架以避免死循环；
                    # 同时抑制工具路由，避免重复打开浏览器/应用
                    # 🔥 将所有框架执行步骤的完整结果传递给主Agent
                    if collected_info:
                        # 将所有步骤结果汇总，每步最多2000字符
                        context_parts = []
                        for idx, key in enumerate(sorted(collected_info.keys())):
                            step_result = collected_info[key]
                            # 限制每步长度，避免上下文过长
                            max_length = 2000 if len(collected_info) > 1 else 5000  # 单步任务可以更长
                            if len(step_result) > max_length:
                                step_result = step_result[:max_length] + "..."
                            context_parts.append(f"【步骤 {idx+1}】\n{step_result}")
                        
                        full_context = "\n\n".join(context_parts)
                        self.base_agent.framework_context = f"框架执行结果：\n{full_context}"
                        print(f"📋 [传递上下文] 已将 {len(collected_info)} 步结果传递给主Agent（总长度: {len(full_context)} 字符）")
                    
                    final_answer = self.base_agent.process_command(user_input, skip_framework=True, suppress_tool_routing=True)
                    return final_answer
                finally:
                    self.base_agent.config["enable_web_search"] = original_search_flag
            
            else:
                return f"未知操作：{action}"
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"执行失败：{str(e)}"
    
    def _should_adjust_framework(self, user_input: str, collected_info: Dict, remaining_steps: List, current_step_result: str = "") -> bool:
        """
        判断是否需要调整框架
        
        Args:
            user_input: 用户输入
            collected_info: 已收集的信息
            remaining_steps: 剩余步骤
            current_step_result: 当前步骤的执行结果
            
        Returns:
            是否需要调整
        """
        # 🔒 如果HexStrike AI已经规划或执行了攻击链，不允许调整其规划步骤
        has_hexstrike_planning = any(
            s.get("action") in ["use_hexstrike_intelligence", "execute_hexstrike_attack_chain"]
            for s in self.completed_steps
        )
        if has_hexstrike_planning:
            # HexStrike AI已规划或执行，不允许调整
            return False
        
        # 检查最后一步是否失败
        if self.completed_steps:
            last_result = self.completed_steps[-1].get("result", "")
            # 如果最后一步失败（包含"失败"、"错误"等关键词），需要调整
            if any(keyword in last_result for keyword in ["失败", "错误", "❌", "无法", "不存在"]):
                return True
        
        # 如果已完成步骤超过5步，检查一次
        if len(self.completed_steps) == 5:
            return True
        return False
    
    def _adjust_framework(self, user_input: str, collected_info: Dict, remaining_steps: List, current_step_result: str = "") -> List[Dict]:
        """
        调整执行框架
        
        Args:
            user_input: 用户输入
            collected_info: 已收集的信息
            remaining_steps: 原剩余步骤
            current_step_result: 当前步骤的执行结果
            
        Returns:
            新的步骤列表
        """
        # 🔒 如果HexStrike AI已经规划或执行了攻击链，不允许调整其规划步骤
        has_hexstrike_planning = any(
            s.get("action") in ["use_hexstrike_intelligence", "execute_hexstrike_attack_chain"]
            for s in self.completed_steps
        )
        if has_hexstrike_planning:
            # HexStrike AI已规划或执行，不允许调整，只返回原剩余步骤
            return remaining_steps
        
        # 检查已完成步骤中是否有HexStrike AI规划
        has_hexstrike_planning = any(
            s.get("action") == "use_hexstrike_intelligence" 
            for s in self.completed_steps
        )
        
        if has_hexstrike_planning:
            # HexStrike AI已经规划过，只允许添加传递步骤，不允许调整攻击步骤
            # 如果剩余步骤中已经有pass_to_main_agent，就不需要调整
            if any(s.get("action") == "pass_to_main_agent" for s in remaining_steps):
                return remaining_steps  # 不调整，保持原样
            else:
                # 只添加传递步骤，不调整其他步骤
                return remaining_steps + [
                    {
                        "description": "将HexStrike AI规划结果传递给主Agent",
                        "action": "pass_to_main_agent",
                        "params": {}
                    }
                ]
        prompt = f"""你是任务规划专家，需要根据当前进展调整执行框架。

原始用户请求：{user_input}

已完成的步骤：
{self._format_completed_steps()}

已收集的信息：
{json.dumps(collected_info, ensure_ascii=False, indent=2)}

原计划的剩余步骤：
{json.dumps(remaining_steps, ensure_ascii=False, indent=2)}

请根据当前进展，重新规划后续步骤。返回JSON数组格式，例如：
[
    {{"description": "整合信息并回答", "action": "answer_question", "params": {{}}}}
]

如果不需要调整，返回原剩余步骤。
"""
        
        # 直接调用OpenAI API
        try:
            import openai
            
            if "deepseek" in self.intent_model:
                api_key = self.base_agent.config.get("deepseek_key", "")
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com/v1"
                )
            else:
                api_key = self.base_agent.config.get("openai_key", "")
                client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model=self.intent_model,
                messages=[
                    {"role": "system", "content": "你是任务规划专家，根据进展调整执行计划。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7,
                timeout=15
            )
            
            response = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ API调用失败: {e}")
            return remaining_steps
        
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            return json.loads(response)
        except:
            return remaining_steps
    
    def _format_completed_steps(self) -> str:
        """格式化已完成的步骤"""
        if not self.completed_steps:
            return "（暂无）"
        
        lines = []
        for step in self.completed_steps:
            lines.append(f"[第 {step['step']} 步] {step['description']}")
        return "\n".join(lines)
    
    def _generate_final_answer(self, user_input: str, collected_info: Dict) -> str:
        """
        生成最终答案 - 框架Agent只负责协调，不负责回答
        
        Args:
            user_input: 用户输入
            collected_info: 收集的所有信息
            
        Returns:
            最终回答
        """
        # 检查最后一步是否已经是回答或传递给主Agent
        if self.completed_steps:
            last_step = self.completed_steps[-1]
            last_action = last_step.get("action", "")  # 🔥 改为检查action而非description
            
            # 🔥 如果最后一步的action是pass_to_main_agent，说明已经调用过主Agent
            if last_action == "pass_to_main_agent":
                # 最后一步已经完成回答，直接返回
                print("✅ 最后一步已是pass_to_main_agent，直接返回结果，不再重复调用")
                return last_step["result"]
        
            # 兼容旧的检查方式
            last_description = last_step.get("description", "").lower()
            if any(keyword in last_description for keyword in ["answer", "回答", "主agent", "传递"]):
                print("✅ 最后一步包含回答关键词，直接返回结果")
                return last_step["result"]
        
        # 如果最后一步不是pass_to_main_agent，强制调用主Agent处理
        print("⚠️ 框架未以pass_to_main_agent结束，强制调用主Agent处理")
        
        # 将框架执行结果注入到主Agent的上下文中
        context_summary = "\n\n".join([
            f"【步骤 {step['step']}】{step['description']}\n{step['result'][:500]}" 
            for step in self.completed_steps
        ])
        
        self.base_agent.framework_context = f"框架执行结果：\n{context_summary}"
        
        # 调用主Agent，让它基于框架执行结果生成回答
        return self.base_agent.process_command(user_input, skip_framework=True, suppress_tool_routing=True)
    
    def _is_security_test_task(self, user_input: str) -> bool:
        """
        检测是否是安全测试任务（不依赖关键词，直接判断）
        
        Args:
            user_input: 用户输入
            
        Returns:
            是否是安全测试任务
        """
        # 不依赖关键词，直接检查是否有HexStrike AI可用
        # 如果有HexStrike AI可用，且用户输入包含目标（URL、IP、域名），就认为是安全测试任务
        try:
            mcp_server = self.base_agent.mcp_tools.server
            if not hasattr(mcp_server, 'hexstrike_mcp_client') or not mcp_server.hexstrike_mcp_client:
                return False
            
            # 检查是否包含目标（URL、IP、域名）
            import re
            url_pattern = r'https?://[^\s]+'
            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            domain_pattern = r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
            
            has_target = (
                re.search(url_pattern, user_input) or
                re.search(ip_pattern, user_input) or
                re.search(domain_pattern, user_input)
            )
            
            # 如果包含目标，且HexStrike AI可用，就认为是安全测试任务
            return has_target and mcp_server.hexstrike_mcp_client.is_available()
        except:
            return False
    
    def _create_hexstrike_intelligence_framework(self, user_input: str) -> List[Dict[str, Any]]:
        """
        创建使用HexStrike AI智能规划的框架（直接传递用户请求，不依赖关键词）
        
        Args:
            user_input: 用户输入
            
        Returns:
            框架列表
        """
        print("🔍 [目标提取] 开始从用户输入中提取目标...")
        # 从用户输入中提取目标（URL、IP或域名），保留中文部分并翻译成英文
        import re
        
        # 先提取完整目标（包括中文部分）
        # URL模式：匹配http(s)://开头，到空格或行尾
        url_pattern = r'https?://[^\s]+'
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        domain_pattern = r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
        
        target = None
        url_match = re.search(url_pattern, user_input)
        if url_match:
            # 提取完整URL（包括后面的中文）
            url_start = url_match.start()
            # 找到URL后的中文部分（直到遇到空格或标点）
            url_end = url_match.end()
            # 继续匹配后面的中文字符和标点
            remaining = user_input[url_end:]
            chinese_part = ""
            for char in remaining:
                if char.isspace():
                    break
                if '\u4e00' <= char <= '\u9fff' or char in '，。！？、；：':
                    chinese_part += char
            target = user_input[url_start:url_end] + chinese_part
        else:
            ip_match = re.search(ip_pattern, user_input)
            if ip_match:
                target = ip_match.group(0)
            else:
                domain_match = re.search(domain_pattern, user_input)
                if domain_match:
                    target = domain_match.group(0)
        
        # 如果没有找到明确目标，将整个用户输入作为目标
        if not target:
            target = user_input
            print(f"⚠️ [目标提取] 未找到明确目标，使用整个用户输入作为目标")
        else:
            print(f"✅ [目标提取] 已提取目标: {target}")
        
        # 构建objective，如果目标包含中文，在objective中说明需要翻译
        # 让HexStrike AI自己处理翻译（通过提示词）
        if re.search(r'[\u4e00-\u9fff]', target):
            # 目标包含中文，在objective中说明需要翻译目标中的中文部分
            objective = f"{user_input}\n\nNote: The target contains Chinese characters. Please translate the Chinese part to English while keeping URLs/IPs/domains unchanged. For example, if the target is 'https://example.com的HTML源码', translate it to 'https://example.com HTML source code'."
            print(f"🌐 [目标处理] 目标包含中文，已添加翻译说明")
        else:
            objective = user_input
        
        print(f"📋 [框架构建] 构建HexStrike AI智能规划框架...")
        print(f"   - 目标: {target}")
        print(f"   - 任务描述: {objective[:100]}...")
        
        # 直接使用 execute-attack-chain，让HexStrike AI规划并执行攻击链，然后返回执行报告
        # 将用户输入作为objective传递给HexStrike AI，让它理解任务意图
        framework = [
            {
                "description": "启动HexStrike AI服务器",
                "action": "start_hexstrike_ai",
                "params": {}
            },
            {
                "description": "使用HexStrike AI执行攻击链（规划并执行，返回执行报告）",
                "action": "execute_hexstrike_attack_chain",
                "params": {
                    "target": target,  # 保留原始目标（包含中文）
                    "objective": objective  # 在objective中说明需要翻译
                }
            },
            {
                "description": "将HexStrike AI执行报告传递给主Agent",
                "action": "pass_to_main_agent",
                "params": {}
            }
        ]
        
        return framework


# 测试代码
if __name__ == "__main__":
    print("框架ReAct Agent模块加载成功")

