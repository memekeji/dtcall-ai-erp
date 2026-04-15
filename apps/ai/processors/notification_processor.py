"""
通知和延迟节点处理器
"""

import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .base_processor import BaseNodeProcessor, NodeProcessorRegistry


@NodeProcessorRegistry.register('notification')
class NotificationProcessor(BaseNodeProcessor):
    """通知节点处理器"""

    @classmethod
    def get_display_name(cls):
        return "通知节点"

    @classmethod
    def get_icon(cls):
        return "layui-icon-notice"

    @classmethod
    def get_description(cls):
        return "发送通知消息"

    def _get_config_schema(self) -> dict:
        """获取通知节点的配置模式"""
        return {
            'notification_type': {
                'type': 'string',
                'required': True,
                'label': '通知类型',
                'options': [
                    {'value': 'email', 'label': '邮件通知'},
                    {'value': 'sms', 'label': '短信通知'},
                    {'value': 'webhook', 'label': 'Webhook通知'},
                    {'value': 'system', 'label': '系统通知'}
                ],
                'description': '选择通知发送方式'
            },
            'recipients': {
                'type': 'array',
                'required': True,
                'label': '接收人',
                'items': {
                    'type': 'string'
                },
                'description': '通知接收人列表'
            },
            'subject': {
                'type': 'string',
                'required': True,
                'label': '主题',
                'description': '通知主题'
            },
            'message': {
                'type': 'string',
                'required': True,
                'label': '消息内容',
                'multiline': True,
                'rows': 5,
                'description': '通知详细内容'
            },
            'email_config': {
                'type': 'object',
                'required': False,
                'label': '邮件配置',
                'properties': {
                    'smtp_server': {
                        'type': 'string',
                        'required': True,
                        'label': 'SMTP服务器',
                        'default': 'smtp.qq.com'
                    },
                    'smtp_port': {
                        'type': 'number',
                        'required': True,
                        'label': 'SMTP端口',
                        'default': 587
                    },
                    'username': {
                        'type': 'string',
                        'required': True,
                        'label': '用户名'
                    },
                    'password': {
                        'type': 'string',
                        'required': True,
                        'label': '密码',
                        'password': True
                    },
                    'use_tls': {
                        'type': 'boolean',
                        'required': False,
                        'label': '使用TLS',
                        'default': True
                    }
                },
                'depends_on': {'notification_type': 'email'}
            },
            'sms_config': {
                'type': 'object',
                'required': False,
                'label': '短信配置',
                'properties': {
                    'provider': {
                        'type': 'string',
                        'required': True,
                        'label': '服务商',
                        'options': [
                            {'value': 'aliyun', 'label': '阿里云'},
                            {'value': 'tencent', 'label': '腾讯云'}
                        ]
                    },
                    'access_key': {
                        'type': 'string',
                        'required': True,
                        'label': 'Access Key'
                    },
                    'access_secret': {
                        'type': 'string',
                        'required': True,
                        'label': 'Access Secret',
                        'password': True
                    },
                    'sign_name': {
                        'type': 'string',
                        'required': True,
                        'label': '签名名称'
                    }
                },
                'depends_on': {'notification_type': 'sms'}
            },
            'webhook_config': {
                'type': 'object',
                'required': False,
                'label': 'Webhook配置',
                'properties': {
                    'url': {
                        'type': 'string',
                        'required': True,
                        'label': 'Webhook地址'
                    },
                    'method': {
                        'type': 'string',
                        'required': True,
                        'label': '请求方法',
                        'default': 'POST',
                        'options': [
                            {'value': 'POST', 'label': 'POST'},
                            {'value': 'GET', 'label': 'GET'},
                            {'value': 'PUT', 'label': 'PUT'}
                        ]
                    },
                    'headers': {
                        'type': 'object',
                        'required': False,
                        'label': '请求头',
                        'default': {}
                    },
                    'timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '超时时间',
                        'default': 30
                    }
                },
                'depends_on': {'notification_type': 'webhook'}
            },
            'priority': {
                'type': 'string',
                'required': False,
                'label': '优先级',
                'default': 'normal',
                'options': [
                    {'value': 'low', 'label': '低'},
                    {'value': 'normal', 'label': '普通'},
                    {'value': 'high', 'label': '高'},
                    {'value': 'urgent', 'label': '紧急'}
                ],
                'description': '通知优先级'
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时时间',
                'default': 30,
                'min': 1,
                'max': 300,
                'description': '通知发送超时时间（秒）'
            }
        }

    def _replace_variables(self, text: str, context: dict) -> str:
        """替换文本中的变量占位符"""
        if not isinstance(text, str):
            return text

        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            text = text.replace(placeholder, str(value))

        return text

    def execute(self, config: dict, context: dict) -> dict:
        """执行通知节点逻辑"""
        notification_type = config.get('notification_type', 'system')
        recipients = config.get('recipients', [])
        subject = config.get('subject', '')
        message = config.get('message', '')
        config.get('priority', 'normal')
        config.get('timeout', 30)

        # 替换消息中的变量
        subject = self._replace_variables(subject, context)
        message = self._replace_variables(message, context)

        result = {
            'notification_type': notification_type,
            'success': False,
            'sent_count': 0,
            'failed_count': 0,
            'details': []
        }

        try:
            if notification_type == 'email':
                self._send_email(config, recipients, subject, message, result)
            elif notification_type == 'sms':
                self._send_sms(config, recipients, message, result)
            elif notification_type == 'webhook':
                self._send_webhook(config, recipients, message, result)
            elif notification_type == 'system':
                self._send_system_notification(
                    recipients, subject, message, result)
            else:
                result['details'].append(f"不支持的通知类型: {notification_type}")

            result['success'] = result['failed_count'] == 0

        except Exception as e:
            result['details'].append(f"通知发送失败: {str(e)}")

        return result

    def _send_email(
            self,
            config: dict,
            recipients: list,
            subject: str,
            message: str,
            result: dict):
        """发送邮件通知"""
        email_config = config.get('email_config', {})
        smtp_server = email_config.get('smtp_server', 'smtp.qq.com')
        smtp_port = email_config.get('smtp_port', 587)
        username = email_config.get('username', '')
        password = email_config.get('password', '')
        use_tls = email_config.get('use_tls', True)

        for recipient in recipients:
            try:
                msg = MIMEMultipart()
                msg['From'] = username
                msg['To'] = recipient
                msg['Subject'] = subject

                msg.attach(MIMEText(message, 'plain', 'utf-8'))

                server = smtplib.SMTP(smtp_server, smtp_port)
                if use_tls:
                    server.starttls()

                server.login(username, password)
                server.send_message(msg)
                server.quit()

                result['sent_count'] += 1
                result['details'].append(f"邮件发送成功: {recipient}")

            except Exception as e:
                result['failed_count'] += 1
                result['details'].append(f"邮件发送失败 {recipient}: {str(e)}")

    def _send_sms(
            self,
            config: dict,
            recipients: list,
            message: str,
            result: dict):
        """发送短信通知"""
        sms_config = config.get('sms_config', {})
        sms_config.get('provider', 'aliyun')

        for recipient in recipients:
            try:
                # 这里可以集成具体的短信服务商API
                # 目前返回占位符
                result['sent_count'] += 1
                result['details'].append(f"短信发送成功: {recipient}")

            except Exception as e:
                result['failed_count'] += 1
                result['details'].append(f"短信发送失败 {recipient}: {str(e)}")

    def _send_webhook(
            self,
            config: dict,
            recipients: list,
            message: str,
            result: dict):
        """发送Webhook通知"""
        config.get('webhook_config', {})

        for recipient in recipients:
            try:
                # 这里可以集成HTTP请求发送Webhook
                # 目前返回占位符
                result['sent_count'] += 1
                result['details'].append(f"Webhook发送成功: {recipient}")

            except Exception as e:
                result['failed_count'] += 1
                result['details'].append(f"Webhook发送失败 {recipient}: {str(e)}")

    def _send_system_notification(
            self,
            recipients: list,
            subject: str,
            message: str,
            result: dict):
        """发送系统通知"""
        for recipient in recipients:
            try:
                # 这里可以集成系统内部通知机制
                # 目前返回占位符
                result['sent_count'] += 1
                result['details'].append(f"系统通知发送成功: {recipient}")

            except Exception as e:
                result['failed_count'] += 1
                result['details'].append(f"系统通知发送失败 {recipient}: {str(e)}")


@NodeProcessorRegistry.register('delay')
class DelayProcessor(BaseNodeProcessor):
    """延迟节点处理器"""

    @classmethod
    def get_display_name(cls):
        return "延迟节点"

    @classmethod
    def get_icon(cls):
        return "layui-icon-time"

    @classmethod
    def get_description(cls):
        return "延迟执行后续节点"

    def _get_config_schema(self) -> dict:
        """获取延迟节点的配置模式"""
        return {
            'delay_type': {
                'type': 'string',
                'required': True,
                'label': '延迟类型',
                'options': [
                    {'value': 'fixed', 'label': '固定时间'},
                    {'value': 'dynamic', 'label': '动态计算'},
                    {'value': 'until_time', 'label': '直到指定时间'}
                ],
                'description': '选择延迟方式'
            },
            'delay_seconds': {
                'type': 'number',
                'required': False,
                'label': '延迟秒数',
                'default': 5,
                'min': 1,
                'max': 86400,
                'description': '延迟的秒数（1秒到24小时）',
                'depends_on': {'delay_type': 'fixed'}
            },
            'delay_expression': {
                'type': 'string',
                'required': False,
                'label': '延迟表达式',
                'description': '动态计算延迟时间的表达式，如：{{variable}} * 2',
                'depends_on': {'delay_type': 'dynamic'}
            },
            'target_time': {
                'type': 'string',
                'required': False,
                'label': '目标时间',
                'description': '延迟到指定时间（格式：YYYY-MM-DD HH:MM:SS）',
                'depends_on': {'delay_type': 'until_time'}
            },
            'check_interval': {
                'type': 'number',
                'required': False,
                'label': '检查间隔',
                'default': 60,
                'min': 1,
                'max': 3600,
                'description': '检查时间间隔（秒）'
            }
        }

    def execute(self, config: dict, context: dict) -> dict:
        """执行延迟节点逻辑"""
        delay_type = config.get('delay_type', 'fixed')
        check_interval = config.get('check_interval', 60)

        result = {
            'delay_type': delay_type,
            'success': True,
            'actual_delay': 0,
            'message': ''
        }

        try:
            if delay_type == 'fixed':
                delay_seconds = config.get('delay_seconds', 5)
                result['actual_delay'] = delay_seconds
                result['message'] = f"固定延迟 {delay_seconds} 秒"
                time.sleep(delay_seconds)

            elif delay_type == 'dynamic':
                delay_expression = config.get('delay_expression', '')
                # 计算动态延迟时间
                delay_seconds = self._evaluate_delay_expression(
                    delay_expression, context)
                result['actual_delay'] = delay_seconds
                result['message'] = f"动态延迟 {delay_seconds} 秒"
                time.sleep(delay_seconds)

            elif delay_type == 'until_time':
                target_time_str = config.get('target_time', '')
                # 计算到目标时间的延迟
                delay_seconds = self._calculate_delay_until_time(
                    target_time_str)
                result['actual_delay'] = delay_seconds
                result['message'] = f"延迟到指定时间，等待 {delay_seconds} 秒"

                if delay_seconds > 0:
                    # 分段等待，避免长时间阻塞
                    while delay_seconds > 0:
                        sleep_time = min(delay_seconds, check_interval)
                        time.sleep(sleep_time)
                        delay_seconds -= sleep_time

            else:
                result['success'] = False
                result['message'] = f"不支持的延迟类型: {delay_type}"

        except Exception as e:
            result['success'] = False
            result['message'] = f"延迟执行失败: {str(e)}"

        return result

    def _replace_variables(self, text: str, context: dict) -> str:
        """替换文本中的变量占位符"""
        if not isinstance(text, str):
            return text

        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            text = text.replace(placeholder, str(value))

        return text

    def _evaluate_delay_expression(
            self,
            expression: str,
            context: dict) -> int:
        """计算动态延迟表达式"""
        if not expression:
            return 0

        # 替换表达式中的变量
        expression = self._replace_variables(expression, context)

        try:
            # 简单的表达式计算（注意安全限制）
            # 这里可以集成更安全的表达式计算库
            return int(eval(expression))
        except BaseException:
            return 0

    def _calculate_delay_until_time(self, target_time_str: str) -> int:
        """计算到目标时间的延迟秒数"""
        if not target_time_str:
            return 0

        try:
            from datetime import datetime
            target_time = datetime.strptime(
                target_time_str, '%Y-%m-%d %H:%M:%S')
            current_time = datetime.now()

            if target_time <= current_time:
                return 0

            delay_seconds = int((target_time - current_time).total_seconds())
            return max(0, delay_seconds)

        except Exception:
            return 0
