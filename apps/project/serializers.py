from rest_framework import serializers
from .models import Project, ProjectStep, Task, WorkHour, ProjectDocument, ProjectCategory, ProjectStage, WorkType, Comment
from django.contrib.auth import get_user_model

User = get_user_model()

class ProjectCategorySerializer(serializers.ModelSerializer):
    """项目分类序列化器"""
    class Meta:
        model = ProjectCategory
        fields = '__all__'

class ProjectStageSerializer(serializers.ModelSerializer):
    """项目阶段序列化器"""
    class Meta:
        model = ProjectStage
        fields = '__all__'

class WorkTypeSerializer(serializers.ModelSerializer):
    """工作类型序列化器"""
    class Meta:
        model = WorkType
        fields = '__all__'

class ProjectSerializer(serializers.ModelSerializer):
    """项目序列化器"""
    category = ProjectCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=ProjectCategory.objects.all(), source='category')
    manager = serializers.StringRelatedField(read_only=True)
    manager_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=User.objects.all(), source='manager')
    members = serializers.StringRelatedField(many=True, read_only=True)
    members_ids = serializers.PrimaryKeyRelatedField(write_only=True, many=True, queryset=User.objects.all(), source='members')
    creator = serializers.StringRelatedField(read_only=True)
    customer = serializers.StringRelatedField(read_only=True)
    contract = serializers.StringRelatedField(read_only=True)
    department = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Project
        fields = '__all__'
        extra_fields = ['category_id', 'manager_id', 'members_ids']

class ProjectStepSerializer(serializers.ModelSerializer):
    """项目步骤序列化器"""
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=Project.objects.all(), source='project')
    manager = serializers.StringRelatedField(read_only=True)
    manager_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=User.objects.all(), source='manager')
    members = serializers.StringRelatedField(many=True, read_only=True)
    members_ids = serializers.PrimaryKeyRelatedField(write_only=True, many=True, queryset=User.objects.all(), source='members')
    
    class Meta:
        model = ProjectStep
        fields = '__all__'
        extra_fields = ['project_id', 'manager_id', 'members_ids']

class TaskSerializer(serializers.ModelSerializer):
    """任务序列化器"""
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=Project.objects.all(), source='project')
    step = serializers.StringRelatedField(read_only=True)
    step_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=ProjectStep.objects.all(), source='step')
    assignee = serializers.StringRelatedField(read_only=True)
    assignee_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=User.objects.all(), source='assignee')
    participants = serializers.StringRelatedField(many=True, read_only=True)
    participants_ids = serializers.PrimaryKeyRelatedField(write_only=True, many=True, queryset=User.objects.all(), source='participants')
    creator = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Task
        fields = '__all__'
        extra_fields = ['project_id', 'step_id', 'assignee_id', 'participants_ids']

class WorkHourSerializer(serializers.ModelSerializer):
    """工时记录序列化器"""
    task = serializers.StringRelatedField(read_only=True)
    task_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=Task.objects.all(), source='task')
    user = serializers.StringRelatedField(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=User.objects.all(), source='user')
    
    class Meta:
        model = WorkHour
        fields = '__all__'
        extra_fields = ['task_id', 'user_id']

class ProjectDocumentSerializer(serializers.ModelSerializer):
    """项目文档序列化器"""
    project = serializers.StringRelatedField(read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(write_only=True, queryset=Project.objects.all(), source='project')
    creator = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = ProjectDocument
        fields = '__all__'
        extra_fields = ['project_id']


class CommentSerializer(serializers.ModelSerializer):
    """评论序列化器"""
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    content_type_id = serializers.IntegerField(write_only=True, required=False)
    content_type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = ['id', 'user_id', 'username', 'content_type_id', 'content', 'content_type', 'content_type_display', 'object_id', 'parent', 'parent_id', 'create_time', 'update_time']
    
    def get_content_type_display(self, obj):
        return obj.content_type.name
    
    def validate_content_type_id(self, value):
        if value is None:
            return value
        from django.contrib.contenttypes.models import ContentType
        try:
            ContentType.objects.get(id=value)
        except ContentType.DoesNotExist:
            raise serializers.ValidationError("Invalid content type ID")
        return value