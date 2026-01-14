import json
import requests
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.conf import settings
from ..models import DataSource, DataMapping, DataCollection, ProductionDataPoint, Equipment

logger = logging.getLogger(__name__)


class DataCollectorService:
    """数据采集服务"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Production-Data-Collector/1.0'
        })
    

    
    def _test_api_connection(self, data_source: DataSource) -> Dict[str, Any]:
        """测试API连接"""
        try:
            logger.info(f"正在测试API数据源连接: {data_source.name} ({data_source.code})")
            
            url = data_source.endpoint_url
            method = data_source.request_method.upper()
            headers = data_source.request_headers.copy()
            params = data_source.request_params.copy()
            
            auth = self._prepare_auth(data_source, headers)
            
            logger.debug(f"API请求: {method} {url}")
            
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data_source.request_body if method in ['POST', 'PUT', 'PATCH'] else None,
                timeout=data_source.timeout,
                auth=auth
            )
            
            logger.info(f"API连接测试成功: {data_source.name}, 状态码: {response.status_code}")
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response_size': len(response.content),
                'content_type': response.headers.get('Content-Type', ''),
                'sample_data': response.text[:500] if response.text else ''
            }
            
        except requests.exceptions.Timeout as e:
            logger.error(f"API连接超时: {data_source.name}, 错误: {str(e)}")
            return {
                'success': False,
                'error': f'请求超时: {str(e)}'
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API连接错误: {data_source.name}, 错误: {str(e)}")
            return {
                'success': False,
                'error': f'网络连接失败: {str(e)}'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {data_source.name}, 错误: {str(e)}")
            return {
                'success': False,
                'error': f'HTTP请求失败: {str(e)}'
            }
    
    def _test_iot_connection(self, data_source: DataSource) -> Dict[str, Any]:
        """测试IoT设备连接"""
        try:
            logger.info(f"正在测试IoT数据源连接: {data_source.name} ({data_source.code})")
            
            import socket
            
            host = data_source.host
            port = data_source.port
            
            if not host or not port:
                logger.warning(f"IoT数据源配置不完整: {data_source.name}")
                return {
                    'success': False,
                    'error': 'IoT设备需要配置主机地址和端口'
                }
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(data_source.timeout)
            
            logger.debug(f"尝试连接IoT设备: {host}:{port}")
            
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                logger.info(f"IoT设备连接成功: {data_source.name} ({host}:{port})")
                return {
                    'success': True,
                    'message': f'成功连接到 {host}:{port}'
                }
            else:
                logger.warning(f"IoT设备连接失败: {data_source.name} ({host}:{port})")
                return {
                    'success': False,
                    'error': f'无法连接到 {host}:{port}'
                }
                
        except socket.timeout:
            logger.error(f"IoT连接超时: {data_source.name}")
            return {
                'success': False,
                'error': '连接超时'
            }
        except Exception as e:
            logger.error(f"IoT连接测试失败: {data_source.name}, 错误: {str(e)}")
            return {
                'success': False,
                'error': f'IoT连接测试失败: {str(e)}'
            }
    
    def _test_mqtt_connection(self, data_source: DataSource) -> Dict[str, Any]:
        """测试MQTT连接"""
        try:
            # 这里需要安装paho-mqtt库
            # pip install paho-mqtt
            import paho.mqtt.client as mqtt
            
            def on_connect(client, userdata, flags, rc):
                userdata['connected'] = rc == 0
                userdata['rc'] = rc
            
            client = mqtt.Client()
            userdata = {'connected': False, 'rc': -1}
            client.user_data_set(userdata)
            client.on_connect = on_connect
            
            if data_source.username and data_source.password:
                client.username_pw_set(data_source.username, data_source.password)
            
            client.connect(data_source.host, data_source.port or 1883, data_source.timeout)
            client.loop_start()
            
            # 等待连接结果
            timeout = time.time() + data_source.timeout
            while time.time() < timeout and not userdata['connected'] and userdata['rc'] == -1:
                time.sleep(0.1)
            
            client.loop_stop()
            client.disconnect()
            
            if userdata['connected']:
                return {
                    'success': True,
                    'message': f'成功连接到MQTT服务器 {data_source.host}:{data_source.port or 1883}'
                }
            else:
                return {
                    'success': False,
                    'error': f'MQTT连接失败，返回码: {userdata["rc"]}'
                }
                
        except ImportError:
            return {
                'success': False,
                'error': 'MQTT功能需要安装paho-mqtt库: pip install paho-mqtt'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'MQTT连接测试失败: {str(e)}'
            }
    
    def _test_modbus_connection(self, data_source: DataSource) -> Dict[str, Any]:
        """测试Modbus连接"""
        try:
            # 这里需要安装pymodbus库
            # pip install pymodbus
            from pymodbus.client import ModbusTcpClient
            
            client = ModbusTcpClient(
                host=data_source.host,
                port=data_source.port or 502,
                timeout=data_source.timeout
            )
            
            if client.connect():
                # 尝试读取一个寄存器来测试连接
                result = client.read_holding_registers(0, 1, unit=1)
                client.close()
                
                if not result.isError():
                    return {
                        'success': True,
                        'message': f'成功连接到Modbus设备 {data_source.host}:{data_source.port or 502}'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Modbus读取失败: {str(result)}'
                    }
            else:
                return {
                    'success': False,
                    'error': f'无法连接到Modbus设备 {data_source.host}:{data_source.port or 502}'
                }
                
        except ImportError:
            return {
                'success': False,
                'error': 'Modbus功能需要安装pymodbus库: pip install pymodbus'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Modbus连接测试失败: {str(e)}'
            }
    
    def preview_data(self, data_source: DataSource) -> Dict[str, Any]:
        """预览数据源数据"""
        try:
            # 获取原始数据
            raw_data = self._fetch_raw_data(data_source)
            if not raw_data['success']:
                return raw_data
            
            # 解析数据结构
            parsed_data = self._parse_data_structure(raw_data['data'])
            
            # 应用数据映射（如果存在）
            mappings = data_source.mappings.filter(is_active=True)
            mapped_data = {}
            
            if mappings.exists():
                mapped_data = self._apply_mappings(raw_data['data'], mappings)
            
            return {
                'success': True,
                'raw_data': raw_data['data'],
                'parsed_structure': parsed_data,
                'mapped_data': mapped_data,
                'mappings_count': mappings.count()
            }
            
        except Exception as e:
            logger.error(f'数据预览失败: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
    
    def collect_data(self, data_source: DataSource) -> Dict[str, Any]:
        """采集数据"""
        collection = DataCollection.objects.create(
            data_source=data_source,
            status='processing',
            start_time=timezone.now()
        )
        
        try:
            # 获取原始数据
            raw_result = self._fetch_raw_data(data_source)
            
            collection.raw_response = str(raw_result)
            
            if not raw_result['success']:
                collection.status = 'failed'
                collection.error_message = raw_result.get('error', '未知错误')
                collection.end_time = timezone.now()
                collection.duration = (collection.end_time - collection.start_time).total_seconds()
                collection.save()
                return raw_result
            
            collection.raw_data = raw_result['data']
            
            # 应用数据映射
            mappings = data_source.mappings.filter(is_active=True)
            if mappings.exists():
                processed_result = self._process_data(raw_result['data'], mappings, collection)
                collection.processed_data = processed_result['data']
                collection.record_count = processed_result['record_count']
                collection.success_count = processed_result['success_count']
                collection.error_count = processed_result['error_count']
                
                if processed_result['errors']:
                    collection.error_details = processed_result['errors']
            
            # 保存数据点
            if collection.processed_data:
                self._save_data_points(collection)
            
            collection.status = 'success' if collection.error_count == 0 else 'partial'
            collection.end_time = timezone.now()
            collection.duration = (collection.end_time - collection.start_time).total_seconds()
            collection.save()
            
            # 更新数据源状态
            data_source.last_collection_time = collection.collection_time
            data_source.last_success_time = timezone.now()
            data_source.error_count = 0
            data_source.last_error = ''
            data_source.save()
            
            return {
                'success': True,
                'collection_id': collection.id,
                'record_count': collection.record_count,
                'success_count': collection.success_count,
                'error_count': collection.error_count
            }
            
        except Exception as e:
            logger.error(f'数据采集失败: {str(e)}')
            
            collection.status = 'failed'
            collection.error_message = str(e)
            collection.end_time = timezone.now()
            collection.duration = (collection.end_time - collection.start_time).total_seconds()
            collection.save()
            
            # 更新数据源错误状态
            data_source.error_count += 1
            data_source.last_error = str(e)
            data_source.save()
            
            return {
                'success': False,
                'error': str(e),
                'collection_id': collection.id
            }
    
    def _fetch_raw_data(self, data_source: DataSource) -> Dict[str, Any]:
        """获取原始数据"""
        if data_source.source_type == 'api':
            return self._fetch_api_data(data_source)
        elif data_source.source_type == 'iot':
            return self._fetch_iot_data(data_source)
        elif data_source.source_type == 'mqtt':
            return self._fetch_mqtt_data(data_source)
        elif data_source.source_type == 'modbus':
            return self._fetch_modbus_data(data_source)
        else:
            return {
                'success': False,
                'error': f'不支持的数据源类型: {data_source.source_type}'
            }
    
    def _fetch_api_data(self, data_source: DataSource) -> Dict[str, Any]:
        """获取API数据"""
        try:
            url = data_source.endpoint_url
            method = data_source.request_method.upper()
            headers = data_source.request_headers.copy()
            params = data_source.request_params.copy()
            
            # 设置认证
            auth = self._prepare_auth(data_source, headers)
            
            # 发送请求
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data_source.request_body if method in ['POST', 'PUT', 'PATCH'] else None,
                timeout=data_source.timeout,
                auth=auth
            )
            
            response.raise_for_status()
            
            # 尝试解析JSON
            try:
                data = response.json()
            except:
                data = response.text
            
            return {
                'success': True,
                'data': data,
                'status_code': response.status_code,
                'headers': dict(response.headers)
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'API请求失败: {str(e)}'
            }
    
    def _fetch_iot_data(self, data_source: DataSource) -> Dict[str, Any]:
        """获取IoT设备数据"""
        # 这里需要根据具体的IoT协议实现数据获取
        # 示例：TCP Socket通信
        try:
            import socket
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(data_source.timeout)
            sock.connect((data_source.host, data_source.port))
            
            # 发送请求命令（如果有的话）
            if data_source.request_body:
                sock.send(data_source.request_body.encode())
            
            # 接收数据
            data = sock.recv(4096).decode()
            sock.close()
            
            # 尝试解析JSON
            try:
                parsed_data = json.loads(data)
            except:
                parsed_data = data
            
            return {
                'success': True,
                'data': parsed_data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'IoT数据获取失败: {str(e)}'
            }
    
    def _fetch_mqtt_data(self, data_source: DataSource) -> Dict[str, Any]:
        """获取MQTT数据"""
        # MQTT数据通常是订阅模式，这里提供一个简单的实现
        try:
            import paho.mqtt.client as mqtt
            
            received_data = []
            
            def on_message(client, userdata, message):
                try:
                    data = json.loads(message.payload.decode())
                except:
                    data = message.payload.decode()
                
                received_data.append({
                    'topic': message.topic,
                    'data': data,
                    'timestamp': time.time()
                })
            
            client = mqtt.Client()
            client.on_message = on_message
            
            if data_source.username and data_source.password:
                client.username_pw_set(data_source.username, data_source.password)
            
            client.connect(data_source.host, data_source.port or 1883, data_source.timeout)
            
            # 订阅主题（从请求参数中获取）
            topics = data_source.request_params.get('topics', ['#'])
            for topic in topics:
                client.subscribe(topic)
            
            client.loop_start()
            time.sleep(5)  # 等待5秒接收数据
            client.loop_stop()
            client.disconnect()
            
            return {
                'success': True,
                'data': received_data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'MQTT数据获取失败: {str(e)}'
            }
    
    def _fetch_modbus_data(self, data_source: DataSource) -> Dict[str, Any]:
        """获取Modbus数据"""
        try:
            from pymodbus.client import ModbusTcpClient
            
            client = ModbusTcpClient(
                host=data_source.host,
                port=data_source.port or 502,
                timeout=data_source.timeout
            )
            
            if not client.connect():
                return {
                    'success': False,
                    'error': f'无法连接到Modbus设备'
                }
            
            # 从请求参数中获取读取配置
            registers = data_source.request_params.get('registers', [])
            data = {}
            
            for register in registers:
                address = register.get('address', 0)
                count = register.get('count', 1)
                unit = register.get('unit', 1)
                function = register.get('function', 'holding')  # holding, input, coil, discrete
                
                if function == 'holding':
                    result = client.read_holding_registers(address, count, unit=unit)
                elif function == 'input':
                    result = client.read_input_registers(address, count, unit=unit)
                elif function == 'coil':
                    result = client.read_coils(address, count, unit=unit)
                elif function == 'discrete':
                    result = client.read_discrete_inputs(address, count, unit=unit)
                else:
                    continue
                
                if not result.isError():
                    data[f"{function}_{address}"] = result.registers if hasattr(result, 'registers') else result.bits
            
            client.close()
            
            return {
                'success': True,
                'data': data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Modbus数据获取失败: {str(e)}'
            }
    
    def _prepare_auth(self, data_source: DataSource, headers: dict):
        """准备认证信息"""
        auth = None
        
        if data_source.auth_type == 'basic':
            from requests.auth import HTTPBasicAuth
            auth = HTTPBasicAuth(data_source.username, data_source.password)
        elif data_source.auth_type == 'bearer':
            headers['Authorization'] = f'Bearer {data_source.token}'
        elif data_source.auth_type == 'api_key':
            # API Key可以放在header或参数中，这里放在header
            headers['X-API-Key'] = data_source.api_key
        
        return auth
    
    def _parse_data_structure(self, data: Any) -> Dict[str, Any]:
        """解析数据结构"""
        def analyze_value(value, path=""):
            if isinstance(value, dict):
                result = {"type": "object", "path": path, "children": {}}
                for key, val in value.items():
                    child_path = f"{path}.{key}" if path else key
                    result["children"][key] = analyze_value(val, child_path)
                return result
            elif isinstance(value, list):
                result = {"type": "array", "path": path, "length": len(value)}
                if value:
                    result["item_type"] = analyze_value(value[0], f"{path}[0]")
                return result
            elif isinstance(value, str):
                return {"type": "string", "path": path, "sample": value[:50]}
            elif isinstance(value, (int, float)):
                return {"type": "number", "path": path, "value": value}
            elif isinstance(value, bool):
                return {"type": "boolean", "path": path, "value": value}
            else:
                return {"type": "unknown", "path": path, "value": str(value)}
        
        return analyze_value(data)
    
    def _apply_mappings(self, data: Any, mappings) -> Dict[str, Any]:
        """应用数据映射"""
        result = {}
        
        for mapping in mappings:
            try:
                # 根据路径提取数据
                value = self._extract_value_by_path(data, mapping.source_path)
                
                if value is not None:
                    # 应用数据转换
                    transformed_value = self._transform_value(value, mapping)
                    result[mapping.name] = transformed_value
                elif mapping.default_value:
                    result[mapping.name] = mapping.default_value
                
            except Exception as e:
                logger.warning(f'映射字段 {mapping.name} 处理失败: {str(e)}')
                if mapping.default_value:
                    result[mapping.name] = mapping.default_value
        
        return result
    
    def _extract_value_by_path(self, data: Any, path: str) -> Any:
        """根据路径提取值"""
        if not path:
            return data
        
        parts = path.split('.')
        current = data
        
        for part in parts:
            if '[' in part and ']' in part:
                # 处理数组索引，如 items[0]
                key, index_str = part.split('[')
                index = int(index_str.rstrip(']'))
                
                if isinstance(current, dict) and key in current:
                    current = current[key]
                    if isinstance(current, list) and 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                else:
                    return None
            else:
                # 普通字段访问
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
        
        return current
    
    def _transform_value(self, value: Any, mapping) -> Any:
        """转换数据值"""
        if mapping.transform_type == 'none':
            return value
        
        try:
            if mapping.transform_type == 'multiply':
                factor = mapping.transform_params.get('factor', 1)
                return float(value) * factor
            elif mapping.transform_type == 'divide':
                divisor = mapping.transform_params.get('divisor', 1)
                return float(value) / divisor
            elif mapping.transform_type == 'add':
                addend = mapping.transform_params.get('addend', 0)
                return float(value) + addend
            elif mapping.transform_type == 'subtract':
                subtrahend = mapping.transform_params.get('subtrahend', 0)
                return float(value) - subtrahend
            elif mapping.transform_type == 'round':
                digits = mapping.transform_params.get('digits', 2)
                return round(float(value), digits)
            elif mapping.transform_type == 'format':
                format_str = mapping.transform_params.get('format', '{}')
                return format_str.format(value)
            elif mapping.transform_type == 'regex':
                import re
                pattern = mapping.transform_params.get('pattern', '')
                if pattern:
                    match = re.search(pattern, str(value))
                    return match.group(1) if match and match.groups() else value
            
        except Exception as e:
            logger.warning(f'数据转换失败: {str(e)}')
        
        return value
    
    def _process_data(self, raw_data: Any, mappings, collection) -> Dict[str, Any]:
        """处理数据"""
        processed_data = {}
        errors = []
        success_count = 0
        error_count = 0
        
        try:
            # 如果原始数据是数组，处理每个元素
            if isinstance(raw_data, list):
                processed_data = []
                for i, item in enumerate(raw_data):
                    try:
                        mapped_item = self._apply_mappings(item, mappings)
                        processed_data.append(mapped_item)
                        success_count += 1
                    except Exception as e:
                        errors.append(f'第{i+1}条记录处理失败: {str(e)}')
                        error_count += 1
            else:
                # 单个对象
                try:
                    processed_data = self._apply_mappings(raw_data, mappings)
                    success_count = 1
                except Exception as e:
                    errors.append(f'数据处理失败: {str(e)}')
                    error_count = 1
            
            return {
                'data': processed_data,
                'record_count': success_count + error_count,
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors
            }
            
        except Exception as e:
            return {
                'data': {},
                'record_count': 0,
                'success_count': 0,
                'error_count': 1,
                'errors': [str(e)]
            }
    
    def _save_data_points(self, collection: DataCollection):
        """保存数据点"""
        try:
            data = collection.processed_data
            
            # 如果数据是数组，处理每个元素
            if isinstance(data, list):
                for item in data:
                    self._save_single_data_point(item, collection)
            else:
                # 单个对象
                self._save_single_data_point(data, collection)
                
        except Exception as e:
            logger.error(f'保存数据点失败: {str(e)}')
    
    def _save_single_data_point(self, data: dict, collection: DataCollection):
        """保存单个数据点"""
        try:
            # 这里需要根据实际业务逻辑来确定如何保存数据点
            # 示例：假设数据中包含设备ID和指标信息
            
            equipment_id = data.get('equipment_id')
            if not equipment_id:
                return
            
            try:
                equipment = Equipment.objects.get(id=equipment_id)
            except Equipment.DoesNotExist:
                logger.warning(f'设备不存在: {equipment_id}')
                return
            
            # 保存每个指标作为数据点
            for key, value in data.items():
                if key in ['equipment_id', 'timestamp']:
                    continue
                
                # 解析时间戳
                timestamp = data.get('timestamp')
                if timestamp:
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    elif isinstance(timestamp, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp)
                else:
                    timestamp = timezone.now()
                
                ProductionDataPoint.objects.create(
                    equipment=equipment,
                    data_source=collection.data_source,
                    collection=collection,
                    metric_name=key,
                    metric_value=str(value),
                    timestamp=timestamp,
                    collection_time=collection.collection_time
                )
                
        except Exception as e:
            logger.error(f'保存单个数据点失败: {str(e)}')