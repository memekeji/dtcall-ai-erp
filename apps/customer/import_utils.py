import logging
import re
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Customer, Contact, CustomerField, CustomerCustomFieldValue

logger = logging.getLogger(__name__)


class CustomerImportProcessor:
    """客户导入处理器"""

    def __init__(self):
        self.custom_fields = {}
        self.custom_fields_by_name = {}
        self.custom_fields_by_normalized_name = {}
        self._load_custom_fields()

    def _load_custom_fields(self):
        """加载所有自定义字段"""
        fields = CustomerField.objects.filter(status=True, delete_time=0)

        for field in fields:
            # 按字段代码索引
            self.custom_fields[field.code] = field
            # 按字段名称索引（不区分大小写）
            self.custom_fields_by_name[field.name.lower()] = field
            # 按规范化名称索引（与前端保持一致）
            normalized_name = re.sub(r'\s+', '', field.name.strip().lower())
            self.custom_fields_by_normalized_name[normalized_name] = field

    def process_import_data(self, table_data, header_map):
        """处理导入数据"""
        # 默认表头映射
        default_header_map = {
            '客户名称': 'name',
            '联系人姓名': 'contact_person',
            '联系电话': 'phone',
            '职位': 'position',
            '联系人邮箱': 'email',
            '地址': 'address'
        }

        # 合并映射
        final_header_map = {**default_header_map, **header_map}

        error_rows = []
        valid_data = []

        # 为每条数据添加错误原因字段
        for item in table_data:
            item['error_reason'] = ''

        # 验证和处理每条数据
        for index, item in enumerate(table_data, start=1):
            try:
                processed_item = self._process_single_item(
                    item, final_header_map, index)
                if processed_item:
                    valid_data.append(processed_item)
            except ValidationError as e:
                error_messages = []
                if hasattr(e, 'message_dict'):
                    for field, messages in e.message_dict.items():
                        error_messages.extend(
                            [f'{field}: {msg}' for msg in messages])
                else:
                    error_messages = e.messages

                item['error_reason'] = '; '.join(error_messages)
                item['row_index'] = index
                error_rows.append(item)
                logger.warning(f'数据验证失败: 行{index}, 错误: {item["error_reason"]}')

        return valid_data, error_rows

    def _process_single_item(self, item, header_map, index):
        """处理单条数据"""
        # 映射表头
        mapped_item = {}
        custom_field_data = {}

        for original_key, value in item.items():
            if original_key == 'error_reason':
                continue

            # 获取映射后的键名
            mapped_key = header_map.get(original_key, original_key)
            mapped_item[mapped_key] = value

            # 检查是否为自定义字段
            custom_field = self._find_custom_field(original_key, mapped_key)
            if custom_field:
                custom_field_data[custom_field.code] = {
                    'field': custom_field,
                    'value': value
                }

        # 获取Customer模型字段
        model_fields = [field.name for field in Customer._meta.get_fields()]

        # 分离客户数据和联系人数据
        contact_fields = ['contact_person', 'phone', 'position', 'email']
        customer_data = {}
        contact_data = {}

        for key, value in mapped_item.items():
            if key in model_fields and key not in contact_fields:
                customer_data[key] = value
            elif key in contact_fields:
                contact_data[key] = value

        # 设置默认值
        customer_data.setdefault('name', '')
        customer_data.setdefault('address', '')

        # 验证必填字段
        if not customer_data.get('name', '').strip():
            raise ValidationError('客户名称不能为空')

        # 检查重复
        if Customer.objects.filter(
                name=customer_data['name'],
                delete_time=0).exists():
            raise ValidationError('客户名称已存在')

        # 创建客户对象（不保存）
        customer = Customer(**customer_data)
        customer.full_clean()

        return {
            'customer': customer,
            'contact_data': contact_data,
            'custom_field_data': custom_field_data,
            'original_item': mapped_item
        }

    def _find_custom_field(self, original_key, mapped_key):
        """查找自定义字段"""
        # 1. 通过字段代码匹配
        if mapped_key in self.custom_fields:
            return self.custom_fields[mapped_key]

        # 2. 通过原始键名匹配（不区分大小写）
        if original_key.lower() in self.custom_fields_by_name:
            return self.custom_fields_by_name[original_key.lower()]

        # 3. 通过规范化名称匹配
        normalized_original = re.sub(r'\s+', '', original_key.strip().lower())
        if normalized_original in self.custom_fields_by_normalized_name:
            return self.custom_fields_by_normalized_name[normalized_original]

        # 4. 通过映射键名匹配（不区分大小写）
        if mapped_key.lower() in self.custom_fields_by_name:
            return self.custom_fields_by_name[mapped_key.lower()]

        return None

    def save_import_data(self, valid_data):
        """保存导入数据"""
        saved_count = 0
        failed_count = 0

        try:
            with transaction.atomic():
                for item_data in valid_data:
                    try:
                        # 保存客户
                        customer = item_data['customer']
                        customer.save()

                        # 保存联系人
                        contact_data = item_data['contact_data']
                        if contact_data.get(
                                'contact_person') or contact_data.get('phone'):
                            contact = Contact(
                                customer=customer,
                                contact_person=contact_data.get(
                                    'contact_person', ''),
                                phone=contact_data.get('phone', ''),
                                position=contact_data.get('position', ''),
                                email=contact_data.get('email') or None,
                                is_primary=True
                            )
                            contact.save()

                        # 保存自定义字段
                        custom_field_data = item_data['custom_field_data']
                        for field_code, field_info in custom_field_data.items():
                            field = field_info['field']
                            value = field_info['value']

                            # 转换字段值
                            converted_value = self._convert_field_value(
                                field, value)

                            # 创建自定义字段值
                            custom_value = CustomerCustomFieldValue(
                                customer=customer,
                                field=field,
                                value=converted_value
                            )
                            custom_value.save()

                        saved_count += 1

                    except Exception as e:
                        logger.error(f'保存单条数据失败: {str(e)}')
                        failed_count += 1
                        raise  # 重新抛出异常以触发事务回滚
        except Exception as e:
            logger.error(f'批量保存失败: {str(e)}')
            raise
        return saved_count, failed_count

    def _convert_field_value(self, field, value):
        """转换字段值"""
        if value is None or value == '':
            return ''

        if field.field_type == 'int':
            try:
                return str(int(value))
            except (ValueError, TypeError):
                return str(value)
        elif field.field_type == 'float':
            try:
                return str(float(value))
            except (ValueError, TypeError):
                return str(value)
        elif field.field_type == 'bool':
            if isinstance(value, bool):
                return str(value).lower()
            elif isinstance(value, str):
                return 'true' if value.lower() in [
                    'true', '1', 'yes', '是'] else 'false'
            else:
                return 'false'
        elif field.field_type == 'date':
            try:
                if isinstance(value, (int, float)):
                    return timezone.datetime.fromtimestamp(
                        value).strftime('%Y-%m-%d')
                else:
                    return str(value)
            except Exception:
                return str(value)
        elif field.field_type == 'datetime':
            try:
                if isinstance(value, (int, float)):
                    return timezone.datetime.fromtimestamp(
                        value).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    return str(value)
            except Exception:
                return str(value)
        else:
            return str(value)
