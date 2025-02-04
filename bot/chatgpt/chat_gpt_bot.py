# encoding:utf-8

import base64
import time
import os
import string
import random
import io
from minio import Minio
from minio.error import S3Error

import openai
import openai.error
import requests
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.fastgpt.fastgpt_client import FastGPTClient
from common.log import logger
from config import conf, load_config
from common import const
from bot.bot import Bot
from bot.chatgpt.chat_gpt_session import ChatGPTSession
from bot.openai.open_ai_image import OpenAIImage
from bot.openai.open_ai_vision import OpenAIVision
from bot.session_manager import SessionManager
from common.token_bucket import TokenBucket
from common import memory, utils
from bot.baidu.baidu_wenxin_session import BaiduWenxinSession

# OpenAI对话模型API (可用)
class ChatGPTBot(Bot, OpenAIImage, OpenAIVision):
    def __init__(self):
        super().__init__()
        # set the default api_key
        openai.api_key = conf().get("open_ai_api_key")
        if conf().get("open_ai_api_base"):
            openai.api_base = conf().get("open_ai_api_base")
        proxy = conf().get("proxy")
        if proxy:
            openai.proxy = proxy
        if conf().get("rate_limit_chatgpt"):
            self.tb4chatgpt = TokenBucket(conf().get("rate_limit_chatgpt", 20))
        conf_model = conf().get("model") or "gpt-3.5-turbo"
        self.sessions = SessionManager(ChatGPTSession, model=conf().get("model") or "gpt-3.5-turbo")
        # o1相关模型不支持system prompt，暂时用文心模型的session

        self.args = {
            "model": conf_model,  # 对话模型的名称
            "temperature": conf().get("temperature", 0.9),  # 值在[0,1]之间，越大表示回复越具有不确定性
            # "max_tokens":4096,  # 回复最大的字符数
            "top_p": conf().get("top_p", 1),
            "frequency_penalty": conf().get("frequency_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            "presence_penalty": conf().get("presence_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            "request_timeout": conf().get("request_timeout", None),  # 请求超时时间，openai接口默认设置为600，对于难问题一般需要较长时间
            "timeout": conf().get("request_timeout", None),  # 重试超时时间，在这个时间内，将会自动重试
        }
        # o1相关模型固定了部分参数，暂时去掉
        if conf_model in [const.O1, const.O1_MINI]:
            self.sessions = SessionManager(BaiduWenxinSession, model=conf().get("model") or const.O1_MINI)
            remove_keys = ["temperature", "top_p", "frequency_penalty", "presence_penalty"]
            for key in remove_keys:
                self.args.pop(key, None)  # 如果键不存在，使用 None 来避免抛出错误

    def reply(self, query, context=None):
        """回复消息
        
        Args:
            query: 查询
            context: 上下文
            
        Returns:
            Reply: 回复对象
        """
        try:
            logger.info(f"[CHATGPT] 收到消息，类型：{context.type}, 内容：{query}")
            
            # 如果是图片消息，只保存不处理
            if context.type == ContextType.IMAGE:
                logger.info("[CHATGPT] 收到图片消息，保存图片路径")
                session_id = context.get("session_id")
                if session_id not in self.sessions.sessions:
                    self.sessions.build_session(session_id)
                session = self.sessions.sessions[session_id]
                if not hasattr(session, 'last_image'):
                    session.last_image = None
                session.last_image = context.content
                logger.info(f"[CHATGPT] 保存图片路径到会话：{context.content}")
                return Reply(ReplyType.TEXT, '')  # 不返回任何消息
            
            # 如果是文本消息
            elif context.type == ContextType.TEXT:
                logger.info(f"[CHATGPT] 处理文本消息：{query}")
                # 检查是否为图片分析触发词
                image_analysis_triggers = ["图片分析", "分析图片", "识别图片", "图片识别", "分析报告", "报告分析"]
                has_trigger = any(trigger in query for trigger in image_analysis_triggers)
                logger.info(f"[CHATGPT] 触发词检查结果：{has_trigger}")
                
                if has_trigger:
                    # 获取会话中保存的图片路径
                    session_id = context.get("session_id")
                    logger.info(f"[CHATGPT] 当前会话ID：{session_id}")
                    
                    if session_id not in self.sessions.sessions:
                        logger.error("[CHATGPT] 未找到会话")
                        return Reply(ReplyType.ERROR, "请先发送要分析的图片")
                    
                    session = self.sessions.sessions[session_id]
                    image_path = getattr(session, 'last_image', None)
                    logger.info(f"[CHATGPT] 从会话获取图片路径：{image_path}")
                    
                    if not image_path:
                        logger.error("[CHATGPT] 未找到图片路径")
                        return Reply(ReplyType.ERROR, "请先发送要分析的图片")
                    
                    if not os.path.exists(image_path):
                        logger.error(f"[CHATGPT] 图片文件不存在：{image_path}")
                        return Reply(ReplyType.ERROR, "图片文件不存在，请重新发送")
                    
                    file_size = os.path.getsize(image_path)
                    logger.info(f"[CHATGPT] 图片大小：{file_size/1024:.2f}KB")
                    
                    # 检查图片大小限制
                    max_size = conf().get("image_max_size", 10485760)  # 默认10MB
                    if file_size > max_size:
                        logger.error(f"[CHATGPT] 图片大小超过限制：{file_size/1024/1024:.2f}MB > {max_size/1024/1024:.2f}MB")
                        return Reply(ReplyType.ERROR, f"图片大小超过限制，最大允许{max_size/1024/1024:.2f}MB")
                    
                    # 上传到OSS
                    try:
                        if conf().get("oss_base_url"):
                            logger.info("[CHATGPT] 开始上传图片到 OSS...")
                            logger.info(f"[CHATGPT] OSS配置: base_url={conf().get('oss_base_url')}, bucket={conf().get('oss_bucket_name')}")
                            
                            image_ext = os.path.splitext(image_path)[1].lower() or '.jpg'
                            content_type = self._get_content_type(image_ext)
                            logger.info(f"[CHATGPT] 文件信息: ext={image_ext}, content_type={content_type}")
                            
                            with open(image_path, 'rb') as f:
                                file_content = f.read()
                                timestamp = int(time.time())
                                random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
                                new_filename = f"{timestamp}_{random_str}{image_ext}"
                                logger.info(f"[CHATGPT] 准备上传文件: {new_filename}")
                                
                                image_url = self._upload_to_oss(file_content, new_filename, content_type)
                                logger.info(f"[CHATGPT] OSS上传成功，URL: {image_url}")
                        else:
                            logger.info("[CHATGPT] 未配置OSS，使用base64格式")
                            image_ext = os.path.splitext(image_path)[1].lower() or '.jpg'
                            content_type = self._get_content_type(image_ext)
                            logger.info(f"[CHATGPT] 文件信息: ext={image_ext}, content_type={content_type}")
                            
                            with open(image_path, 'rb') as img_file:
                                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                                logger.info(f"[CHATGPT] Base64编码完成，长度：{len(img_base64)}")
                                image_url = f"data:{content_type};base64,{img_base64}"
                    except Exception as e:
                        logger.error(f"[CHATGPT] 图片处理失败：{e}")
                        return Reply(ReplyType.ERROR, f"图片处理失败：{str(e)}")
                    
                    # 准备FastGPT API请求
                    message_content = [
                        {
                            "type": "text",
                            "text": "请分析这张图片"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                    
                    chat_id = f"user_{context.get('from_user_id')}_session_{context.get('session_id')}"
                    if len(chat_id) >= 250:
                        chat_id = f"u_{context.get('from_user_id')[:10]}_s_{context.get('session_id')[:10]}"
                    
                    response_chat_item_id = f"resp_{int(time.time())}_{random.choices(string.ascii_letters + string.digits, k=6)}"
                    
                    request_body = {
                        "chatId": chat_id,
                        "stream": False,
                        "messages": [
                            {
                                "role": "user",
                                "content": message_content
                            }
                        ],
                        "detail": False,
                        "variables": {
                            "uid": context.get("from_user_id", ""),
                            "name": context.get("from_user_id", ""),
                            "session_id": context.get("session_id", "")
                        },
                        "responseChatItemId": response_chat_item_id
                    }
                    
                    logger.debug(f"[CHATGPT] FastGPT API请求体：{request_body}")
                    
                    # 调用FastGPT API
                    try:
                        logger.info("[CHATGPT] 开始调用FastGPT API...")
                        client = FastGPTClient()
                        response = client.chat_completion(**request_body)
                        
                        if "error" in response:
                            error_msg = response['error']
                            logger.error(f"[CHATGPT] FastGPT API调用失败：{error_msg}")
                            return Reply(ReplyType.ERROR, f"分析失败：{error_msg}")
                        
                        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                        if not content:
                            logger.error("[CHATGPT] FastGPT API返回内容为空")
                            return Reply(ReplyType.ERROR, "未能获取分析结果")
                        
                        # 保存会话历史
                        self.sessions.session_reply(content, context.get("session_id"), 0)
                        logger.info("[CHATGPT] 分析完成，已保存会话历史")
                        return Reply(ReplyType.TEXT, content)
                            
                    except Exception as e:
                        logger.error(f"[CHATGPT] API调用失败：{e}")
                        return Reply(ReplyType.ERROR, f"API调用失败：{str(e)}")
                else:
                    # 不是触发词，直接处理普通对话
                    logger.info("[CHATGPT] 进入普通对话流程")
                    session = self.sessions.session_query(query, context.get("session_id"))
                    return self.reply_text(context.get("session_id"), session, None, self.args)
            
            # 处理文本消息
            session_id = context["session_id"]
            from_user_id = context.get("from_user_id", "")
            
            # 处理其他请求
            reply = None
            if reply is None:
                session = self.sessions.session_query(query, context.get("session_id"))
                reply = self.reply_text(context.get("session_id"), session, None, self.args)
            
            return reply
                    
        except Exception as e:
                # 处理异常
                logger.exception(f"[CHATGPT] 处理请求异常：{e}")
                return Reply(ReplyType.ERROR, f"处理请求失败：{str(e)}")

    def reply_text(self, session_id: str, session: ChatGPTSession, api_key=None, args=None, retry_count=0) -> dict:
        """
        call openai's ChatCompletion to get the answer
        :param session: a conversation session
        :param session_id: session id
        :param retry_count: retry count
        :return: {}
        """
        try:
            if conf().get("rate_limit_chatgpt") and not self.tb4chatgpt.get_token():
                raise openai.error.RateLimitError("RateLimitError: rate limit exceeded")
            # if api_key == None, the default openai.api_key will be used
            if args is None:
                args = self.args

            # 检查是否需要进行视觉分析
            res = self.do_vision_completion_if_need(session_id, session.messages[-1]['content'])
            if res:
                return res

            # 准备请求参数
            if conf().get("use_fastgpt"):
                # 生成响应消息ID
                response_chat_item_id = f"resp_{int(time.time())}_{random.choices(string.ascii_letters + string.digits, k=6)}"
                
                # 为 FastGPT API 准备参数
                chat_id = f"wx_{session_id}"  # 生成 wx_ 开头的 chatId
                if len(chat_id) >= 250:
                    chat_id = chat_id[:250]  # 截断以确保符合要求
                
                # 准备变量
                variables = {
                    "chat_type": "group" if "@@" in session_id else "private",
                    "session_id": session_id,
                    "user_id": session_id.split("@@")[0] if "@@" in session_id else session_id
                }
                
                logger.info(f"[CHATGPT] 使用 FastGPT API，chat_id: {chat_id}, chat_type: {variables['chat_type']}")
                
                # 调用 FastGPT API
                client = FastGPTClient()
                response = client.chat_completion(
                    messages=session.messages,
                    chat_id=chat_id,
                    response_chat_item_id=response_chat_item_id,
                    variables=variables,
                    detail=False
                )
                
                if "error" in response:
                    error_msg = response['error']
                    logger.error(f"[CHATGPT] FastGPT API调用失败：{error_msg}")
                    return {"completion_tokens": 0, "content": f"API调用失败：{error_msg}"}
                
                content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not content:
                    logger.error("[CHATGPT] FastGPT API返回内容为空")
                    return {"completion_tokens": 0, "content": "未能获取回复内容"}
                
                total_tokens = response.get("usage", {}).get("total_tokens", 0)
                completion_tokens = response.get("usage", {}).get("completion_tokens", 0)
                
                logger.info(f"[CHATGPT] FastGPT API响应成功，使用tokens：{total_tokens}")
                return {
                    "total_tokens": total_tokens,
                    "completion_tokens": completion_tokens,
                    "content": content
                }
            else:
                # 使用普通的 OpenAI API
                response = openai.ChatCompletion.create(
                    api_key=api_key,
                    messages=session.messages,
                    **args
                )

                logger.debug(f"[CHATGPT] API响应：{response}")
                content = response.choices[0]["message"]["content"]

                # 处理工具调用格式
                if isinstance(content, list):
                    tool_content = []
                    for item in content:
                        if item.get("type") == "tool":
                            for tool in item.get("tools", []):
                                tool_content.append(f"{tool.get('toolName', '')}: {tool.get('content', '')}")
                    content = "\n".join(tool_content)

                total_tokens = response["usage"]["total_tokens"] if "usage" in response else 0
                logger.info(f"[CHATGPT] 回复内容：{content}，使用tokens：{total_tokens}")

                return {
                    "total_tokens": total_tokens,
                    "completion_tokens": response["usage"]["completion_tokens"] if "usage" in response else 0,
                    "content": content
                }

        except openai.error.RateLimitError as e:
            logger.warning(f"[CHATGPT] 触发速率限制：{e}")
            return {"completion_tokens": 0, "content": "提问太快啦，请休息一下再问我吧"}

        except openai.error.APIError as e:
            logger.error(f"[CHATGPT] API错误：{e}")
            return {"completion_tokens": 0, "content": "抱歉，服务器出现问题，请稍后再试"}

        except openai.error.Timeout as e:
            logger.warning(f"[CHATGPT] 请求超时：{e}")
            return {"completion_tokens": 0, "content": "请求超时，请稍后再试"}

        except Exception as e:
            logger.exception(f"[CHATGPT] 处理请求异常：{e}")
            if retry_count < 2:
                logger.warn(f"[CHATGPT] 第{retry_count+1}次重试")
                time.sleep(3)
                return self.reply_text(session_id, session, api_key, args, retry_count + 1)
            return {"completion_tokens": 0, "content": f"处理请求失败：{str(e)}"}

    def _upload_to_oss(self, data, filename, content_type):
        """上传文件到OSS"""
        try:
            # 获取OSS配置
            base_url = conf().get("oss_base_url")
            access_key = conf().get("oss_access_key")
            secret_key = conf().get("oss_secret_key")
            bucket_name = conf().get("oss_bucket_name")
            
            logger.info(f"[CHATGPT] OSS配置检查: base_url={base_url}, bucket={bucket_name}")
            
            if not all([base_url, access_key, secret_key, bucket_name]):
                raise Exception("OSS配置不完整")
            
            # 创建MinIO客户端
            endpoint = base_url.replace("https://", "").replace("http://", "")
            secure = base_url.startswith("https://")
            logger.info(f"[CHATGPT] 创建MinIO客户端: endpoint={endpoint}, secure={secure}")
            
            client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            
            # 确保存储桶存在
            full_bucket_name = f"{access_key}-{bucket_name}"
            logger.info(f"[CHATGPT] 检查存储桶: {full_bucket_name}")
            
            try:
                if not client.bucket_exists(full_bucket_name):
                    client.make_bucket(full_bucket_name)
                    logger.info(f"[CHATGPT] 创建存储桶：{full_bucket_name}")
                else:
                    logger.info(f"[CHATGPT] 存储桶已存在：{full_bucket_name}")
            except Exception as e:
                logger.warning(f"[CHATGPT] 检查存储桶失败：{str(e)}")
                # 继续尝试上传，因为可能是权限问题导致无法检查存储桶
            
            # 上传文件
            logger.info(f"[CHATGPT] 开始上传文件: {filename}, content_type={content_type}")
            result = client.put_object(
                full_bucket_name,
                filename,
                io.BytesIO(data),
                len(data),
                content_type=content_type
            )
            logger.info(f"[CHATGPT] 文件上传成功: etag={result.etag}, version_id={result.version_id}")
            
            # 生成URL
            url = f"{base_url}/{full_bucket_name}/{filename}"
            logger.info(f"[CHATGPT] 生成URL: {url}")
            return url
            
        except Exception as e:
            logger.error(f"[CHATGPT] OSS上传失败：{str(e)}")
            raise e

    def _get_content_type(self, file_ext):
        """获取文件的Content-Type
        
        Args:
            file_ext (str): 文件扩展名
            
        Returns:
            str: Content-Type
        """
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp'
        }
        return content_types.get(file_ext, 'application/octet-stream')


class AzureChatGPTBot(ChatGPTBot):
    """Azure版本的ChatGPTBot"""
    
    def __init__(self):
        super().__init__()
        openai.api_type = "azure"
        openai.api_version = conf().get("azure_api_version", "2023-06-01-preview")
        self.args["deployment_id"] = conf().get("azure_deployment_id")

    def create_img(self, query, context):
        """处理图片分析请求"""
        return super().create_img(query, context)
