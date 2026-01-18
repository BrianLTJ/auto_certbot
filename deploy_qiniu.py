# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "qiniu>=7.17.0",
# ]
# ///
from qiniu import Auth, put_file_v2, etag, BucketManager
import qiniu.config
import os
import tomllib
import tempfile
from pathlib import Path

"""
Config Example
Save to "qiniu_config.toml"
```toml
access_key = "your_access_key"
secret_key = "your_secret_key"
bucket_name = "your_kudo_bucket_name"
```
"""

def load_config():
    """Load configuration from TOML file specified in environment variable."""
    # Get TOML file path from environment variable
    config_file = os.getenv('QINIU_CONFIG_FILE')
    
    if not config_file:
        config_file = "qiniu_config.toml"
    
    config_path = Path(config_file)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    # Load and parse TOML file
    with open(config_path, 'rb') as f:
        config = tomllib.load(f)
    
    # Validate required keys
    required_keys = ['access_key', 'secret_key', 'bucket_name']
    missing_keys = [key for key in required_keys if key not in config]
    
    if missing_keys:
        raise KeyError(f"Missing required config keys: {', '.join(missing_keys)}")
    return config

def upload_acme_challenge(challenge_token: str, challenge_validation: str) -> bool:
    access_key = ""
    secret_key = ""
    bucket_name = ""
    try:
        config = load_config()
        #需要填写你的 Access Key 和 Secret Key
        access_key = config['access_key']
        secret_key = config['secret_key']
        #要上传的空间
        bucket_name = config['bucket_name']
    except Exception as e:
        print(f"Error loading config: {e}")
        return False
    if access_key == "" or secret_key == "" or bucket_name == "":
        print("Invalid config")
        return False
    #构建鉴权对象
    q = Auth(access_key, secret_key)
    #上传后保存的文件名
    upload_path = get_challenge_file_path(challenge_token)
    #make temp file
    validation_tmp_file = tempfile.NamedTemporaryFile(delete_on_close=False)
    validation_tmp_file.write(challenge_validation.encode(encoding='utf-8'))
    validation_tmp_file.close()
    validation_file_path = validation_tmp_file.name

    print(f"Upload to URL: {upload_path}")
    print(f"Validation Tmp File: {validation_file_path}")

    #生成上传 Token，可以指定过期时间等
    token = q.upload_token(bucket_name, upload_path, 3600)
    #要上传文件的本地路径
    ret, info = put_file_v2(token, upload_path, validation_file_path, version='v2')
    print(info)
    assert ret['key'] == upload_path
    assert ret['hash'] == etag(validation_file_path)
    if os.path.exists(validation_file_path):
        os.remove(validation_file_path)
    return True

def delete_acme_challenge(challenge_token: str) -> bool:
    access_key = ""
    secret_key = ""
    bucket_name = ""
    try:
        config = load_config()
        #需要填写你的 Access Key 和 Secret Key
        access_key = config['access_key']
        secret_key = config['secret_key']
        #要上传的空间
        bucket_name = config['bucket_name']
    except Exception as e:
        print(f"Error loading config: {e}")
        return False
    if access_key == "" or secret_key == "" or bucket_name == "":
        print("Invalid config")
        return False
    #构建鉴权对象
    q = Auth(access_key, secret_key)
    bucket_mgr = BucketManager(q)
    file_path = get_challenge_file_path(challenge_token)
    info = bucket_mgr.delete(bucket_name, file_path)
    print(info)


def get_challenge_file_path(challenge_token):
    return f'.well-known/acme-challenge/{challenge_token}'

if __name__ == "__main__":
    print(load_config())
