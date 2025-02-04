#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from channel.chat_channel import ChatChannel
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.fastgpt.fastgpt_message import FastGPTMessage
from common.log import logger
from common.singleton import singleton
from config import conf

@singleton
class FastGPTChannel(ChatChannel):
    """FastGPT 渠道"""

    def __init__(self):
        super().__init__()

    def startup(self):
        """启动通道"""
        logger.info("[FastGPT] 启动 FastGPT 渠道")

    def handle_text(self, msg):
        """处理文本消息"""
        logger.debug(f"[FastGPT] 收到文本消息: {msg}")
        context = self._compose_context(ContextType.TEXT, msg.content, msg=msg)
        if context:
            self.produce(context)
        return context

    def handle_image(self, msg):
        """处理图片消息"""
        logger.debug(f"[FastGPT] 收到图片消息: {msg}")
        context = self._compose_context(ContextType.IMAGE, msg.content, msg=msg)
        if context:
            self.produce(context)
        return context

    def _compose_context(self, ctype: ContextType, content, **kwargs):
        """构建消息上下文"""
        context = Context(ctype, content)
        context.kwargs = kwargs
        msg = kwargs.get("msg")
        if msg:
            context["msg"] = msg
            context["from_user_id"] = msg.from_user_id
            context["session_id"] = msg.session_id
            
            # 生成 FastGPT chat_id，格式：user_{from_user_id}_session_{session_id}
            # 注意：chat_id 长度需要小于 250
            chat_id = f"user_{msg.from_user_id}_session_{msg.session_id}"
            if len(chat_id) >= 250:
                # 如果太长，则使用截断的版本
                chat_id = f"u_{msg.from_user_id[:10]}_s_{msg.session_id[:10]}"
            context["chat_id"] = chat_id
            
            # 生成 response_chat_item_id，格式：resp_{timestamp}_{random}
            import time
            import random
            import string
            timestamp = int(time.time())
            random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            context["response_chat_item_id"] = f"resp_{timestamp}_{random_str}"
            
            # 添加用户自定义变量
            context["variables"] = {
                "uid": msg.from_user_id,
                "name": msg.from_user_id,  # 如果有用户昵称，可以在这里设置
                "session_id": msg.session_id
            }
            
            # 获取用户配置
            user_data = conf().get_user_data(msg.from_user_id)
            context["fastgpt_api_key"] = user_data.get("fastgpt_api_key")  # 支持用户自定义 API Key
            
        return context

    def _send(self, reply: Reply, context: Context):
        """发送回复消息"""
        if reply and reply.type:
            if reply.type == ReplyType.TEXT:
                return self._send_text(reply, context)
            elif reply.type == ReplyType.IMAGE:
                return self._send_image(reply, context)
            elif reply.type == ReplyType.IMAGE_URL:
                return self._send_image_url(reply, context)
            else:
                logger.error(f"[FastGPT] 不支持的消息类型: {reply.type}")
                return False
        return True

    def _send_text(self, reply: Reply, context: Context):
        """发送文本消息"""
        try:
            logger.info(f"[FastGPT] 发送文本消息: {reply.content}")
            # 在这里实现具体的发送逻辑
            return True
        except Exception as e:
            logger.error(f"[FastGPT] 发送文本消息失败: {e}")
            return False

    def _send_image(self, reply: Reply, context: Context):
        """发送图片消息"""
        try:
            logger.info(f"[FastGPT] 发送图片消息")
            # 在这里实现具体的发送逻辑
            return True
        except Exception as e:
            logger.error(f"[FastGPT] 发送图片消息失败: {e}")
            return False

    def _send_image_url(self, reply: Reply, context: Context):
        """发送图片 URL 消息"""
        try:
            logger.info(f"[FastGPT] 发送图片URL消息: {reply.content}")
            # 在这里实现具体的发送逻辑
            return True
        except Exception as e:
            logger.error(f"[FastGPT] 发送图片URL消息失败: {e}")
            return False
