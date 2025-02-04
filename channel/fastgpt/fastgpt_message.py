#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from bridge.context import ContextType
from common.log import logger

class FastGPTMessage:
    """FastGPT 消息对象，用于处理和转换消息格式"""

    def __init__(self, data):
        """初始化消息对象
        
        Args:
            data: FastGPT 原始消息数据
        """
        self.data = data
        self.msg_type = self._get_msg_type()
        self.content = self._get_content()
        self.from_user_id = self._get_from_user_id()
        self.session_id = self._get_session_id()
        
    def _get_msg_type(self):
        """获取消息类型"""
        try:
            msg_type = self.data.get("type", "text")
            if msg_type == "text":
                return ContextType.TEXT
            elif msg_type == "image":
                return ContextType.IMAGE
            else:
                return ContextType.TEXT
        except Exception as e:
            logger.error(f"[FastGPT] 获取消息类型失败: {e}")
            return ContextType.TEXT

    def _get_content(self):
        """获取消息内容"""
        try:
            if self.msg_type == ContextType.TEXT:
                return self.data.get("content", "")
            elif self.msg_type == ContextType.IMAGE:
                return self.data.get("url", "")
            else:
                return str(self.data.get("content", ""))
        except Exception as e:
            logger.error(f"[FastGPT] 获取消息内容失败: {e}")
            return ""

    def _get_from_user_id(self):
        """获取发送者ID"""
        try:
            return self.data.get("from_user_id", "")
        except Exception as e:
            logger.error(f"[FastGPT] 获取发送者ID失败: {e}")
            return ""

    def _get_session_id(self):
        """获取会话ID"""
        try:
            # 生成会话ID，可以根据需要自定义生成规则
            return f"fastgpt_{self.from_user_id}"
        except Exception as e:
            logger.error(f"[FastGPT] 获取会话ID失败: {e}")
            return ""

    def __str__(self):
        return f"FastGPTMessage(type={self.msg_type}, content={self.content}, from={self.from_user_id})"
