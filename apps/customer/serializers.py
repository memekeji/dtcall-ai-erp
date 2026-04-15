from rest_framework import serializers
from .models import CustomerField
import json


class CustomerFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerField
        fields = '__all__'
        read_only_fields = ['create_time', 'update_time', 'code']

    def create(self, validated_data):
        # 从名称生成字段标识
        name = validated_data.get('name')
        if name:
            # 转换为小写，替换非字母数字字符为下划线
            code = 'custom_' + \
                ''.join([c.lower() if c.isalnum() else '_' for c in name])
            # 确保唯一性
            base_code = code
            counter = 1
            while CustomerField.objects.filter(code=code).exists():
                code = f'{base_code}_{counter}'
                counter += 1
            validated_data['code'] = code
        customer_field = CustomerField.objects.create(**validated_data)
        return customer_field

    def validate_options(self, value):
        """验证选项配置是否为有效的格式"""
        field_type = self.initial_data.get('field_type')

        # 如果是文本域类型，直接返回原值
        if field_type == 'textarea':
            return value

        # 只有当field_type为'select'时才进行选项验证
        if value and field_type == 'select':
            parsed_options = []
            try:
                # 尝试解析为JSON数组格式
                options = json.loads(value)
                if not isinstance(options, list):
                    raise serializers.ValidationError("下拉选择类型的选项必须是数组格式")
                for option in options:
                    if not isinstance(
                            option, dict) or 'label' not in option or 'value' not in option:
                        raise serializers.ValidationError(
                            "选项格式应为[{label: '显示文本', value: '值'}, ...]")
                    parsed_options.append(option)
            except json.JSONDecodeError:
                lines = value.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(':', 1)
                    if len(parts) != 2:
                        raise serializers.ValidationError(
                            f"选项 '{line}' 格式不正确，应为 '值:显示文本'")
                    option_value, option_label = parts[0].strip(
                    ), parts[1].strip()
                    parsed_options.append(
                        {'value': option_value, 'label': option_label})

            # 检查选项值的唯一性
            if parsed_options:
                values = [option['value'] for option in parsed_options]
                if len(values) != len(set(values)):
                    raise serializers.ValidationError("选项值不能重复")

            # 将解析后的选项转换为JSON字符串存储
            return json.dumps(parsed_options)

        # 如果不是select类型或者没有值，则直接返回
        return value

    def validate_code(self, value):
        """验证字段标识是否符合规范"""
        if not value or not value.strip():
            raise serializers.ValidationError("字段标识不能为空")
        if not value.islower() or ' ' in value:
            raise serializers.ValidationError("字段标识只能包含小写字母和下划线，不能有空格")
        if not value.startswith(('custom_',)):
            raise serializers.ValidationError("字段标识必须以'custom_'开头")
        return value
