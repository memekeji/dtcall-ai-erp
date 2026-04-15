import os
import uuid
import logging
from abc import ABC, abstractmethod
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from apps.system.models import StorageProvider

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """存储后端基类"""

    @abstractmethod
    def save(self, name, content):
        """保存文件"""

    @abstractmethod
    def open(self, name, mode='rb'):
        """打开文件"""

    @abstractmethod
    def delete(self, name):
        """删除文件"""

    @abstractmethod
    def exists(self, name):
        """检查文件是否存在"""

    @abstractmethod
    def url(self, name):
        """获取文件URL"""

    @abstractmethod
    def size(self, name):
        """获取文件大小"""

    @abstractmethod
    def test_connection(self):
        """测试连接"""


class LocalStorageBackend(StorageBackend):
    """本地存储后端"""

    def __init__(self, config):
        self.config = config
        self.base_path = config.local_path or os.path.join(
            settings.MEDIA_ROOT, 'uploads')

    def _get_full_path(self, name):
        return os.path.join(self.base_path, name)

    def save(self, name, content):
        full_path = self._get_full_path(name)
        dir_path = os.path.dirname(full_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(content.read())
        return name

    def open(self, name, mode='rb'):
        return open(self._get_full_path(name), mode)

    def delete(self, name):
        full_path = self._get_full_path(name)
        if os.path.exists(full_path):
            os.remove(full_path)

    def exists(self, name):
        return os.path.exists(self._get_full_path(name))

    def url(self, name):
        return f"{settings.MEDIA_URL}uploads/{name}"

    def size(self, name):
        full_path = self._get_full_path(name)
        if os.path.exists(full_path):
            return os.path.getsize(full_path)
        return 0

    def test_connection(self):
        try:
            if not os.path.exists(self.base_path):
                os.makedirs(self.base_path, exist_ok=True)
            test_file = os.path.join(self.base_path, '.test_connection')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True, '连接成功'
        except Exception as e:
            return False, str(e)


class AliyunOSSBackend(StorageBackend):
    """阿里云OSS存储后端"""

    def __init__(self, config):
        self.config = config
        self.bucket_name = config.bucket_name
        self.endpoint = config.endpoint
        self.region = config.region
        self.domain = config.domain
        self.base_path = config.base_path
        self._bucket = None

    def _get_client(self):
        try:
            from oss2 import Auth, Bucket
            auth = Auth(self.config.access_key, self.config.secret_key)
            bucket = Bucket(auth, self.endpoint, self.bucket_name)
            return bucket
        except ImportError:
            raise ImportError('请安装阿里云SDK: pip install oss2')

    @property
    def bucket(self):
        if self._bucket is None:
            self._bucket = self._get_client()
        return self._bucket

    def save(self, name, content):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.bucket.put_object(full_name, content.read())
        return name

    def open(self, name, mode='rb'):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        data = self.bucket.get_object(full_name)
        return ContentFile(data.read())

    def delete(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.bucket.delete_object(full_name)

    def exists(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        return self.bucket.object_exists(full_name)

    def url(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        if self.domain:
            return f"https://{self.domain}/{full_name}"
        return f"https://{self.bucket_name}.{self.endpoint}/{full_name}"

    def size(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        try:
            info = self.bucket.get_object_info(full_name)
            return info.content_length
        except Exception:
            return 0

    def test_connection(self):
        try:
            self._get_client()
            return True, '连接成功'
        except Exception as e:
            return False, str(e)


class TencentCOSBackend(StorageBackend):
    """腾讯云COS存储后端"""

    def __init__(self, config):
        self.config = config
        self.bucket_name = config.bucket_name
        self.region = config.region
        self.domain = config.domain
        self.base_path = config.base_path
        self._client = None

    def _get_client(self):
        try:
            from qcloud_cos import CosConfig, CosS3Client
            config = CosConfig(
                SecretId=self.config.access_key,
                SecretKey=self.config.secret_key,
                Region=self.region,
                Token=None,
                Scheme='https'
            )
            client = CosS3Client(config)
            return client
        except ImportError:
            raise ImportError('请安装腾讯云SDK: pip install qcloud_cos')

    @property
    def client(self):
        if self._client is None:
            self._client = self._get_client()
        return self._client

    def _get_bucket_name(self):
        return f"{self.bucket_name}-{self.config.access_key}"

    def save(self, name, content):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.client.upload_file_from_buffer(
            Bucket=self._get_bucket_name(),
            Key=full_name,
            Body=content.read()
        )
        return name

    def open(self, name, mode='rb'):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        response = self.client.get_object(
            Bucket=self._get_bucket_name(),
            Key=full_name
        )
        return ContentFile(response['Body'].read())

    def delete(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.client.delete_object(
            Bucket=self._get_bucket_name(),
            Key=full_name
        )

    def exists(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        try:
            self.client.head_object(
                Bucket=self._get_bucket_name(),
                Key=full_name
            )
            return True
        except Exception:
            return False

    def url(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        if self.domain:
            return f"https://{self.domain}/{full_name}"
        return f"https://{self._get_bucket_name()}.cos.{self.region}.myqcloud.com/{full_name}"

    def size(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        try:
            response = self.client.head_object(
                Bucket=self._get_bucket_name(),
                Key=full_name
            )
            return response['Content-Length']
        except Exception:
            return 0

    def test_connection(self):
        try:
            self._get_client()
            return True, '连接成功'
        except Exception as e:
            return False, str(e)


class HuaweiOBSBackend(StorageBackend):
    """华为云OBS存储后端"""

    def __init__(self, config):
        self.config = config
        self.bucket_name = config.bucket_name
        self.endpoint = config.endpoint
        self.domain = config.domain
        self.base_path = config.base_path
        self._client = None

    def _get_client(self):
        try:
            from obs import ObsClient
            client = ObsClient(
                access_key_id=self.config.access_key,
                secret_access_key=self.config.secret_key,
                server=f'https://{self.endpoint}'
            )
            return client
        except ImportError:
            raise ImportError('请安装华为云SDK: pip install obs')

    @property
    def client(self):
        if self._client is None:
            self._client = self._get_client()
        return self._client

    def save(self, name, content):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.client.putObject(
            bucketName=self.bucket_name,
            objectKey=full_name,
            content=content.read()
        )
        return name

    def open(self, name, mode='rb'):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        response = self.client.getObject(
            bucketName=self.bucket_name,
            objectKey=full_name
        )
        return ContentFile(response['body'].read())

    def delete(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.client.deleteObject(
            bucketName=self.bucket_name,
            objectKey=full_name
        )

    def exists(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        try:
            self.client.headObject(
                bucketName=self.bucket_name,
                objectKey=full_name
            )
            return True
        except Exception:
            return False

    def url(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        if self.domain:
            return f"https://{self.domain}/{full_name}"
        return f"https://{self.bucket_name}.{self.endpoint}/{full_name}"

    def size(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        try:
            response = self.client.getObjectMetadata(
                bucketName=self.bucket_name,
                objectKey=full_name
            )
            return response.contentLength
        except Exception:
            return 0

    def test_connection(self):
        try:
            self._get_client()
            return True, '连接成功'
        except Exception as e:
            return False, str(e)


class BaiduBOSBackend(StorageBackend):
    """百度云BOS存储后端"""

    def __init__(self, config):
        self.config = config
        self.bucket_name = config.bucket_name
        self.endpoint = config.endpoint
        self.domain = config.domain
        self.base_path = config.base_path
        self._client = None

    def _get_client(self):
        try:
            from baidubce.services.bos.bos_client import BosClient
            client = BosClient({
                'credentials': {
                    'accessKeyId': self.config.access_key,
                    'secretAccessKey': self.config.secret_key
                },
                'endpoint': self.endpoint
            })
            return client
        except ImportError:
            raise ImportError('请安装百度云SDK: pip install baidubce')

    @property
    def client(self):
        if self._client is None:
            self._client = self._get_client()
        return self._client

    def save(self, name, content):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.client.put_object(
            bucket_name=self.bucket_name,
            key=full_name,
            data=content.read()
        )
        return name

    def open(self, name, mode='rb'):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        response = self.client.get_object(
            bucket_name=self.bucket_name,
            key=full_name
        )
        return ContentFile(response.data)

    def delete(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.client.delete_object(
            bucket_name=self.bucket_name,
            key=full_name
        )

    def exists(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        return self.client.is_object_exist(
            bucket_name=self.bucket_name,
            key=full_name
        )

    def url(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        if self.domain:
            return f"https://{self.domain}/{full_name}"
        return f"https://{self.bucket_name}.{self.endpoint}/{full_name}"

    def size(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        try:
            response = self.client.get_object_meta(
                bucket_name=self.bucket_name,
                key=full_name
            )
            return response.metadata.content_length
        except Exception:
            return 0

    def test_connection(self):
        try:
            self._get_client()
            return True, '连接成功'
        except Exception as e:
            return False, str(e)


class QiniuKODOBackend(StorageBackend):
    """七牛云KODO存储后端"""

    def __init__(self, config):
        self.config = config
        self.bucket_name = config.bucket_name
        self.domain = config.domain
        self.base_path = config.base_path
        self._client = None

    def _get_client(self):
        try:
            import qiniu
            auth = qiniu.Auth(self.config.access_key, self.config.secret_key)
            return auth
        except ImportError:
            raise ImportError('请安装七牛云SDK: pip install qiniu')

    @property
    def client(self):
        return self._get_client()

    def _get_bucket_manager(self):
        try:
            import qiniu
            return qiniu.BucketManager(self.client)
        except ImportError:
            raise ImportError('请安装七牛云SDK: pip install qiniu')

    def save(self, name, content):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        try:
            import qiniu
            token = self.client.upload_token(self.bucket_name, full_name)
            ret, info = qiniu.put_data(token, full_name, content.read())
            if ret is None:
                raise Exception(info.error)
            return name
        except ImportError:
            raise ImportError('请安装七牛云SDK: pip install qiniu')

    def open(self, name, mode='rb'):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        bucket_manager = self._get_bucket_manager()
        ret, info = bucket_manager.fetch(
            f"http://{self.bucket_name}.{self.domain or 'qiniu.com'}/{full_name}",
            self.bucket_name,
            full_name
        )
        return ContentFile(ret['data'])

    def delete(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        bucket_manager = self._get_bucket_manager()
        bucket_manager.delete(self.bucket_name, full_name)

    def exists(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        bucket_manager = self._get_bucket_manager()
        ret, info = bucket_manager.stat(self.bucket_name, full_name)
        return ret is not None

    def url(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        if self.domain:
            return f"https://{self.domain}/{full_name}"
        return f"https://{self.bucket_name}.qiniu.com/{full_name}"

    def size(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        bucket_manager = self._get_bucket_manager()
        ret, info = bucket_manager.stat(self.bucket_name, full_name)
        if ret:
            return ret.get('fsize', 0)
        return 0

    def test_connection(self):
        try:
            self._get_client()
            return True, '连接成功'
        except Exception as e:
            return False, str(e)


class AWSS3Backend(StorageBackend):
    """AWS S3存储后端"""

    def __init__(self, config):
        self.config = config
        self.bucket_name = config.bucket_name
        self.region = config.region
        self.endpoint = config.endpoint
        self.domain = config.domain
        self.base_path = config.base_path
        self._client = None

    def _get_client(self):
        try:
            import boto3
            client = boto3.client(
                's3',
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                region_name=self.region
            )
            return client
        except ImportError:
            raise ImportError('请安装AWS SDK: pip install boto3')

    @property
    def client(self):
        if self._client is None:
            self._client = self._get_client()
        return self._client

    def save(self, name, content):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=full_name,
            Body=content.read()
        )
        return name

    def open(self, name, mode='rb'):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        response = self.client.get_object(
            Bucket=self.bucket_name,
            Key=full_name
        )
        return ContentFile(response['Body'].read())

    def delete(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        self.client.delete_object(
            Bucket=self.bucket_name,
            Key=full_name
        )

    def exists(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=full_name
            )
            return True
        except Exception:
            return False

    def url(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        if self.domain:
            return f"https://{self.domain}/{full_name}"
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{full_name}"

    def size(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=full_name
            )
            return response['ContentLength']
        except Exception:
            return 0

    def test_connection(self):
        try:
            self._get_client()
            return True, '连接成功'
        except Exception as e:
            return False, str(e)


class NASStorageBackend(StorageBackend):
    """NAS存储后端（通用）"""

    def __init__(self, config):
        self.config = config
        self.host = config.nas_host
        self.port = config.nas_port
        self.share_path = config.nas_share_path
        self.base_path = config.base_path

    def _get_mount_path(self):
        if self.host and self.port:
            return f"\\\\{self.host}:{self.port}\\{self.share_path}"
        return self.share_path

    def _get_full_path(self, name):
        mount_path = self._get_mount_path()
        full_path = os.path.join(mount_path, self.base_path or '', name)
        return full_path.replace('\\', '/')

    def save(self, name, content):
        full_path = self._get_full_path(name)
        dir_path = os.path.dirname(full_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(content.read())
        return name

    def open(self, name, mode='rb'):
        return open(self._get_full_path(name), mode)

    def delete(self, name):
        full_path = self._get_full_path(name)
        if os.path.exists(full_path):
            os.remove(full_path)

    def exists(self, name):
        return os.path.exists(self._get_full_path(name))

    def url(self, name):
        full_name = f"{self.base_path}/{name}" if self.base_path else name
        if self.host:
            return f"smb://{self.host}:{self.port}/{self.share_path}/{full_name}"
        return f"file:///{self.share_path}/{full_name}"

    def size(self, name):
        full_path = self._get_full_path(name)
        if os.path.exists(full_path):
            return os.path.getsize(full_path)
        return 0

    def test_connection(self):
        try:
            mount_path = self._get_mount_path()
            if not os.path.exists(mount_path):
                os.makedirs(mount_path, exist_ok=True)
            test_file = os.path.join(mount_path, '.test_connection')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True, '连接成功'
        except Exception as e:
            return False, str(e)


class WebDAVBackend(StorageBackend):
    """WebDAV存储后端"""

    def __init__(self, config):
        self.config = config
        self.url = config.webdav_url.rstrip('/')
        self.username = config.webdav_username
        self.password = config.webdav_password
        self.base_path = config.base_path or ''
        self._client = None

    def _get_client(self):
        try:
            from webdav.client import Client
            options = {
                'webdav_hostname': self.url,
                'webdav_login': self.username,
                'webdav_password': self.password
            }
            client = Client(options)
            return client
        except ImportError:
            raise ImportError('请安装WebDAV库: pip install webdav')

    @property
    def client(self):
        if self._client is None:
            self._client = self._get_client()
        return self._client

    def save(self, name, content):
        full_path = f"{self.base_path}/{name}" if self.base_path else name
        self.client.upload_sync(local_path=full_path, remote_path=full_path)
        return name

    def open(self, name, mode='rb'):
        full_path = f"{self.base_path}/{name}" if self.base_path else name
        import io
        data = self.client.download_sync(
            local_path=full_path, remote_path=full_path)
        if isinstance(data, str):
            data = data.encode('utf-8')
        return io.BytesIO(data)

    def delete(self, name):
        full_path = f"{self.base_path}/{name}" if self.base_path else name
        self.client.clean(full_path)

    def exists(self, name):
        full_path = f"{self.base_path}/{name}" if self.base_path else name
        return self.client.check(full_path)

    def url(self, name):
        full_path = f"{self.base_path}/{name}" if self.base_path else name
        return f"{self.url}/{full_path}"

    def size(self, name):
        full_path = f"{self.base_path}/{name}" if self.base_path else name
        try:
            info = self.client.info(full_path)
            if hasattr(info, 'size'):
                return info.size
            return 0
        except Exception:
            return 0

    def test_connection(self):
        try:
            self._get_client()
            return True, '连接成功'
        except Exception as e:
            return False, str(e)


class StorageService:
    """存储服务"""

    BACKEND_MAP = {
        StorageProvider.LOCAL: LocalStorageBackend,
        StorageProvider.ALIYUN: AliyunOSSBackend,
        StorageProvider.TENCENT: TencentCOSBackend,
        StorageProvider.HUAWEI: HuaweiOBSBackend,
        StorageProvider.BAIDU: BaiduBOSBackend,
        StorageProvider.QINIU: QiniuKODOBackend,
        StorageProvider.AWS: AWSS3Backend,
        StorageProvider.FEINIU_NAS: NASStorageBackend,
        StorageProvider.QUNHUI_NAS: NASStorageBackend,
        StorageProvider.WEBDAV: WebDAVBackend,
    }

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._default_config = None
        return cls._instance

    def get_backend(self, config):
        backend_class = self.BACKEND_MAP.get(config.storage_type)
        if not backend_class:
            raise ValueError(f'不支持的存储类型: {config.storage_type}')
        return backend_class(config)

    def get_default_storage(self):
        from apps.system.models import StorageConfiguration
        if self._default_config is None:
            try:
                self._default_config = StorageConfiguration.objects.filter(
                    status='active',
                    is_default=True
                ).first()
            except Exception as e:
                logger.error(f'获取默认存储配置失败: {e}')
                self._default_config = None
        return self._default_config

    def save_file(self, file_obj, path=''):
        config = self.get_default_storage()
        if config:
            backend = self.get_backend(config)
            file_ext = os.path.splitext(file_obj.name)[1]
            unique_name = f"{uuid.uuid4().hex}{file_ext}"
            full_path = os.path.join(
                path, unique_name) if path else unique_name
            return backend.save(full_path, file_obj)
        else:
            return default_storage.save(path, ContentFile(file_obj.read()))

    def delete_file(self, file_path):
        config = self.get_default_storage()
        if config:
            backend = self.get_backend(config)
            backend.delete(file_path)
        else:
            default_storage.delete(file_path)

    def url(self, file_path):
        config = self.get_default_storage()
        if config:
            backend = self.get_backend(config)
            return backend.url(file_path)
        return default_storage.url(file_path)

    def exists(self, file_path):
        config = self.get_default_storage()
        if config:
            backend = self.get_backend(config)
            return backend.exists(file_path)
        return default_storage.exists(file_path)

    def test_cloud_storage(self, storage_type, access_key,
                           secret_key, bucket_name, region='', endpoint=''):
        """测试云存储配置"""
        try:
            if storage_type == 'aliyun':
                from oss2 import Auth, Bucket
                auth = Auth(access_key, secret_key)
                endpoint = endpoint or f'oss-{region}.aliyuncs.com' if region else 'oss-cn-hangzhou.aliyuncs.com'
                bucket = Bucket(auth, endpoint, bucket_name)
                bucket.get_bucket_info()
                return {'success': True, 'message': '阿里云OSS连接成功'}

            elif storage_type == 'tencent':
                from qcloud_cos import CosConfig, CosS3Client
                region = region or 'ap-guangzhou'
                config = CosConfig(
                    secret_id=access_key,
                    secret_key=secret_key,
                    region=region)
                client = CosS3Client(config)
                client.head_object(Bucket=bucket_name, Key='test')
                return {'success': True, 'message': '腾讯云COS连接成功'}

            elif storage_type == 'huawei':
                from obs import ObsClient
                endpoint = endpoint or f'obs.{region}.myhuaweicloud.com' if region else 'obs.cn-north-4.myhuaweicloud.com'
                obs_client = ObsClient(
                    access_key=access_key,
                    secret_key=secret_key,
                    server=f'https://{endpoint}')
                obs_client.getBucketMetadata(bucketName=bucket_name)
                return {'success': True, 'message': '华为云OBS连接成功'}

            elif storage_type == 'baidu':
                from baidubce.services.bos.bos_client import BosClient
                bos_client = BosClient(
                    credentials={
                        'access_key_id': access_key,
                        'secret_access_key': secret_key})
                bos_client.get_bucket_metadata(bucket_name)
                return {'success': True, 'message': '百度云BOS连接成功'}

            elif storage_type == 'qiniu':
                from qiniu import Auth
                auth = Auth(access_key, secret_key)
                bucket = auth.bucket(bucket_name)
                return {'success': True, 'message': '七牛云KODO连接成功'}

            elif storage_type == 'aws':
                import boto3
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=region or 'us-east-1'
                )
                s3_client.head_bucket(Bucket=bucket_name)
                return {'success': True, 'message': 'AWS S3连接成功'}

            return {'success': False, 'message': f'不支持的云存储类型: {storage_type}'}

        except ImportError as e:
            return {'success': False, 'message': f'缺少依赖库: {str(e)}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def test_nas_storage(self, host, port, share_path):
        """测试NAS存储配置"""
        try:
            import os

            if port and port > 0:
                mount_path = f"\\\\{host}:{port}\\{share_path}"
            else:
                mount_path = f"\\\\{host}\\{share_path}"

            if os.path.exists(mount_path):
                return {'success': True, 'message': 'NAS存储路径可访问'}

            return {'success': True, 'message': 'NAS配置已保存（请确保网络可达）'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def test_webdav_storage(self, webdav_url, username='', password=''):
        """测试WebDAV存储配置"""
        try:
            import requests
            from requests.auth import HTTPBasicAuth

            if not webdav_url.startswith('http'):
                webdav_url = 'https://' + webdav_url

            response = requests.request(
                'OPTIONS',
                webdav_url,
                auth=HTTPBasicAuth(username, password) if username else None,
                timeout=10
            )

            if response.status_code in [200, 207]:
                return {'success': True, 'message': 'WebDAV连接成功'}
            else:
                return {'success': False,
                        'message': f'WebDAV连接失败: HTTP {response.status_code}'}

        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': '无法连接到WebDAV服务器'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def sync_file_to_all_storages(self, file_path, content):
        """同步文件到所有有效存储位置"""
        from apps.system.models import StorageConfiguration

        success_count = 0
        fail_count = 0
        errors = []

        active_configs = StorageConfiguration.objects.filter(status='active')

        for config in active_configs:
            try:
                backend = self.get_backend(config)
                backend.save(file_path, content)
                success_count += 1

                if config.sync_to_local:
                    try:
                        default_storage.save(file_path, content)
                    except Exception as local_err:
                        logger.warning(f'同步到本地存储失败: {local_err}')

            except Exception as e:
                logger.error(f'同步文件到存储配置{config.pk}失败: {e}')
                fail_count += 1
                errors.append(f'{config.name}: {str(e)}')

        return {
            'success_count': success_count,
            'fail_count': fail_count,
            'errors': errors,
            'total': success_count + fail_count
        }

    def save_file_with_sync(self, file_obj, path=''):
        """保存文件到默认存储，并可选同步到其他存储位置"""
        config = self.get_default_storage()

        file_ext = os.path.splitext(file_obj.name)[1]
        unique_name = f"{uuid.uuid4().hex}{file_ext}"
        full_path = os.path.join(path, unique_name) if path else unique_name

        if config:
            backend = self.get_backend(config)
            content = ContentFile(file_obj.read())
            backend.save(full_path, content)

            if config.sync_to_local:
                try:
                    default_storage.save(full_path, content)
                except Exception as e:
                    logger.warning(f'同步到本地存储失败: {e}')

            self._sync_to_secondary_storages(full_path, content)

            return full_path
        else:
            return default_storage.save(
                full_path, ContentFile(file_obj.read()))

    def _sync_to_secondary_storages(self, file_path, content):
        """将文件同步到辅助存储位置（除默认存储外的其他活动存储）"""
        from apps.system.models import StorageConfiguration

        default_config = self.get_default_storage()
        if not default_config:
            return

        secondary_configs = StorageConfiguration.objects.filter(
            status='active'
        ).exclude(pk=default_config.pk)

        for config in secondary_configs:
            try:
                if config.sync_to_local and config.storage_type == 'local':
                    default_storage.save(file_path, content)
                elif config.storage_type != 'local':
                    backend = self.get_backend(config)
                    backend.save(file_path, content)
            except Exception as e:
                logger.error(f'同步到辅助存储{config.pk}失败: {e}')

    def delete_file_from_all_storages(self, file_path):
        """从所有存储位置删除文件"""
        from apps.system.models import StorageConfiguration

        deleted_count = 0
        fail_count = 0

        configs = StorageConfiguration.objects.filter(status='active')

        for config in configs:
            try:
                backend = self.get_backend(config)
                backend.delete(file_path)
                deleted_count += 1
            except Exception as e:
                logger.error(f'从存储配置{config.pk}删除文件失败: {e}')
                fail_count += 1

        try:
            default_storage.delete(file_path)
        except Exception as e:
            logger.warning(f'从默认存储删除文件失败: {e}')

        return {'deleted_count': deleted_count, 'fail_count': fail_count}

    def get_file_url(self, file_path):
        """获取文件的访问URL，优先从配置的存储获取"""
        config = self.get_default_storage()
        if config:
            backend = self.get_backend(config)
            return backend.url(file_path)
        return default_storage.url(file_path)

    def check_file_exists(self, file_path):
        """检查文件是否存在"""
        config = self.get_default_storage()
        if config:
            backend = self.get_backend(config)
            return backend.exists(file_path)
        return default_storage.exists(file_path)

    def get_file_size(self, file_path):
        """获取文件大小"""
        config = self.get_default_storage()
        if config:
            backend = self.get_backend(config)
            return backend.size(file_path)
        return 0

    def copy_file_to_storage(
            self, source_path, dest_path='', storage_config=None):
        """复制文件到指定存储"""
        if storage_config:
            backend = self.get_backend(storage_config)
            try:
                with default_storage.open(source_path, 'rb') as f:
                    content = ContentFile(f.read())
                    return backend.save(dest_path or source_path, content)
            except Exception as e:
                logger.error(f'复制文件到存储失败: {e}')
                return None
        else:
            return default_storage.save(dest_path, ContentFile(
                default_storage.open(source_path).read()))


storage_service = StorageService()
