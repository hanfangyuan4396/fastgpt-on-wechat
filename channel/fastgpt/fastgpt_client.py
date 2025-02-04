#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import requests
import base64
from typing import List, Dict, Optional, Any, Union
from config import conf
from common.log import logger

class FastGPTClient:
    """FastGPT API 客户端"""
    
    def __init__(self):
        """初始化 FastGPT 客户端"""
        self.api_base = conf().get("fastgpt_api_base", "").rstrip('/')
        self.api_key = conf().get("fastgpt_api_key", "")
        if not self.api_base or not self.api_key:
            raise ValueError("FastGPT API 配置不完整，请检查 config.json 中的 fastgpt_api_base 和 fastgpt_api_key")

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头
        
        Returns:
            Dict[str, str]: 包含 Authorization 的请求头
        """
        return {
            "Authorization": f"Bearer {self.api_key}",  # FastGPT 要求使用 Bearer 认证
            "Content-Type": "application/json"
        }

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        chat_id: Optional[str] = None,  # 如果不传入，则不使用 FastGPT 的上下文功能
        response_chat_item_id: Optional[str] = None,  # 本次对话响应消息的 ID
        variables: Optional[Dict[str, str]] = None,  # 模块变量，用于替换模块中的 {{key}}
        detail: bool = False,  # 是否返回中间值
        **kwargs
    ) -> Dict[str, Any]:
        """发送聊天请求
        
        Args:
            messages: 消息历史记录，结构与 GPT 接口 chat 模式一致
            chat_id: 对话ID，如果传入则使用 FastGPT 的上下文功能
            response_chat_item_id: 响应消息ID，确保在当前 chat_id 下唯一
            variables: 模块变量，用于替换模块中的 {{key}}
            detail: 是否返回中间值
            **kwargs: 其他参数
        
        Returns:
            Dict[str, Any]: FastGPT 的响应
        """
        try:
            # 构建基础请求体
            payload = {
                "messages": messages,
                "stream": False,
                "detail": detail
            }
            
            # 添加会话ID（如果不传入则不使用 FastGPT 的上下文功能）
            if chat_id:
                if len(chat_id) >= 250:
                    logger.warning(f"[FastGPT] chat_id 长度超过250: {chat_id}")
                    chat_id = chat_id[:250]  # 截断以确保符合要求
                payload["chatId"] = chat_id
                
            # 添加响应消息ID
            if response_chat_item_id:
                payload["responseChatItemId"] = response_chat_item_id
                
            # 添加模块变量
            if variables:
                payload["variables"] = variables
                
            payload.update(kwargs)
            
            urls_to_try = [
                f"{self.api_base}/chat/completions",
                f"{self.api_base}/v1/chat/completions",
                f"{self.api_base}/api/v1/chat/completions"
            ]
            
            last_error = None
            for url in urls_to_try:
                try:
                    logger.info(f"[FastGPT] 尝试请求URL: {url}")
                    response = requests.post(
                        url,
                        headers=self._get_headers(),
                        json=payload,
                        timeout=conf().get("request_timeout", 180)
                    )
                    
                    if response.status_code == 404:
                        last_error = f"404 错误: {response.text}"
                        continue
                        
                    if response.status_code == 200:
                        return response.json()
                    else:
                        last_error = f"请求失败: status_code={response.status_code}, response={response.text}"
                        continue
                        
                except Exception as e:
                    last_error = f"请求异常: {str(e)}"
                    continue
            
            error_msg = f"FastGPT API 所有请求都失败: {last_error}"
            logger.error(error_msg)
            return {
                "error": error_msg
            }
                
        except Exception as e:
            error_msg = f"FastGPT API 调用异常: {str(e)}"
            logger.error(error_msg)
            return {
                "error": error_msg
            }

    def chat_completion_with_image(
        self,
        messages: List[Dict[str, str]],
        image_data: Union[str, bytes],
        is_base64: bool = False,
        chat_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """发送带图片的聊天请求
        
        Args:
            messages: 消息历史记录
            image_data: 图片数据，可以是URL或base64数据
            is_base64: 是否是base64数据
            chat_id: 会话ID
            **kwargs: 其他参数
        
        Returns:
            Dict[str, Any]: FastGPT 的响应
        """
        try:
            if is_base64:
                if isinstance(image_data, bytes):
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                else:
                    image_base64 = image_data
                image_part = {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            else:
                image_part = {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data
                    }
                }

            payload = {
                "messages": [
                    *messages[:-1],
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": messages[-1]["content"]
                            },
                            image_part
                        ]
                    }
                ],
                "stream": False,
                "detail": False
            }
            
            if chat_id:
                payload["chatId"] = chat_id
                
            payload.update(kwargs)
            
            logger.info(f"[FastGPT] 准备发送图片分析请求")
            
            urls_to_try = [
                f"{self.api_base}/chat/completions",
                f"{self.api_base}/v1/chat/completions",
                f"{self.api_base}/api/v1/chat/completions"
            ]
            
            last_error = None
            for url in urls_to_try:
                try:
                    logger.info(f"[FastGPT] 尝试请求URL: {url}")
                    response = requests.post(
                        url,
                        headers=self._get_headers(),
                        json=payload,
                        timeout=conf().get("request_timeout", 180)
                    )
                    
                    if response.status_code == 404:
                        last_error = f"404 错误: {response.text}"
                        continue
                        
                    if response.status_code == 200:
                        return response.json()
                    else:
                        last_error = f"请求失败: status_code={response.status_code}, response={response.text}"
                        continue
                        
                except Exception as e:
                    last_error = f"请求异常: {str(e)}"
                    continue
            
            error_msg = f"FastGPT API 所有请求都失败: {last_error}"
            logger.error(error_msg)
            return {
                "error": error_msg
            }
                
        except Exception as e:
            error_msg = f"FastGPT API 调用异常: {str(e)}"
            logger.error(error_msg)
            return {
                "error": error_msg
            }
