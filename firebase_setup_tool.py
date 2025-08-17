#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firebase设置工具 - 帮助配置Firebase环境变量和测试连接
"""

import os
import json
import sys
from pathlib import Path

def print_banner():
    """打印工具横幅"""
    print("=" * 60)
    print("🔥 Firebase设置工具 - CSBYBot云存储配置")
    print("=" * 60)
    print()

def get_firebase_credentials():
    """获取Firebase服务账号密钥"""
    print("📋 步骤1: 获取Firebase服务账号密钥")
    print("-" * 40)
    print("1. 访问 https://console.firebase.google.com/")
    print("2. 选择您的项目: csbybot-cloud-storage")
    print("3. 点击左侧齿轮图标 → 项目设置")
    print("4. 点击'服务账号'标签页")
    print("5. 点击'生成新的私钥'")
    print("6. 下载JSON文件")
    print()
    
    # 询问JSON文件路径
    while True:
        json_path = input("请输入下载的JSON文件路径 (或按Enter跳过): ").strip()
        if not json_path:
            print("⚠️  跳过JSON文件配置，请稍后手动设置环境变量")
            return None
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    credentials = json.load(f)
                
                # 验证JSON格式
                required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
                missing_fields = [field for field in required_fields if field not in credentials]
                
                if missing_fields:
                    print(f"❌ JSON文件格式错误，缺少字段: {', '.join(missing_fields)}")
                    continue
                
                print(f"✅ JSON文件验证成功，项目ID: {credentials['project_id']}")
                return credentials
                
            except Exception as e:
                print(f"❌ 读取JSON文件失败: {e}")
                continue
        else:
            print("❌ 文件不存在，请检查路径")
            continue

def create_env_file(credentials, project_id):
    """创建环境变量文件"""
    print("\n📋 步骤2: 创建环境变量文件")
    print("-" * 40)
    
    env_content = f"""# Firebase配置
FIREBASE_CREDENTIALS='{json.dumps(credentials, separators=(',', ':'))}'
FIREBASE_PROJECT_ID={project_id}

# 存储类型配置
STORAGE_TYPE=hybrid  # 可选: local, firebase, hybrid
CACHE_TTL=300  # 缓存过期时间(秒)
SYNC_INTERVAL=60  # 同步间隔(秒)

# 机器人配置 (根据您的机器人数量调整)
BOT1_API_ID=your_bot1_api_id
BOT1_API_HASH=your_bot1_api_hash
BOT1_BOT_TOKEN=your_bot1_bot_token

BOT2_API_ID=your_bot2_api_id
BOT2_API_HASH=your_bot2_api_hash
BOT2_BOT_TOKEN=your_bot2_bot_token

BOT3_API_ID=your_bot3_api_id
BOT3_API_HASH=your_bot3_api_hash
BOT3_BOT_TOKEN=your_bot3_bot_token
"""
    
    # 保存到.env文件
    env_file = Path('.env')
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"✅ 环境变量文件已创建: {env_file.absolute()}")
    print("⚠️  请根据您的实际机器人配置修改API_ID、API_HASH和BOT_TOKEN")
    
    return env_file

def create_render_env_guide():
    """创建Render环境变量配置指南"""
    print("\n📋 步骤3: Render环境变量配置")
    print("-" * 40)
    
    guide_content = """# Render环境变量配置指南

## 在Render控制台中设置以下环境变量:

### Firebase配置
- FIREBASE_CREDENTIALS: 粘贴完整的JSON服务账号密钥
- FIREBASE_PROJECT_ID: csbybot-cloud-storage

### 存储配置
- STORAGE_TYPE: hybrid
- CACHE_TTL: 300
- SYNC_INTERVAL: 60

### 机器人1配置
- BOT1_API_ID: 您的第一个机器人API_ID
- BOT1_API_HASH: 您的第一个机器人API_HASH
- BOT1_BOT_TOKEN: 您的第一个机器人BOT_TOKEN

### 机器人2配置
- BOT2_API_ID: 您的第二个机器人API_ID
- BOT2_API_HASH: 您的第二个机器人API_HASH
- BOT2_BOT_TOKEN: 您的第二个机器人BOT_TOKEN

### 机器人3配置
- BOT3_API_ID: 您的第三个机器人API_ID
- BOT3_API_HASH: 您的第三个机器人API_HASH
- BOT3_BOT_TOKEN: 您的第三个机器人BOT_TOKEN

## 注意事项:
1. FIREBASE_CREDENTIALS必须是完整的JSON字符串
2. 不要在值周围添加引号
3. 确保所有必需的变量都已设置
4. 设置完成后重新部署服务
"""
    
    guide_file = Path('RENDER_ENV_SETUP.md')
    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print(f"✅ Render配置指南已创建: {guide_file.absolute()}")

def test_firebase_connection(credentials, project_id):
    """测试Firebase连接"""
    print("\n📋 步骤4: 测试Firebase连接")
    print("-" * 40)
    
    try:
        # 设置环境变量
        os.environ['FIREBASE_CREDENTIALS'] = json.dumps(credentials)
        os.environ['FIREBASE_PROJECT_ID'] = project_id
        
        # 尝试导入和初始化Firebase
        from firebase_manager import FirebaseManager
        
        print("🔄 正在测试Firebase连接...")
        
        # 创建管理器实例
        manager = FirebaseManager('test_bot')
        
        # 检查连接状态
        health = manager.get_health_status()
        
        if health['is_connected']:
            print("✅ Firebase连接测试成功!")
            print(f"   项目ID: {health['project_id']}")
            print(f"   机器人ID: {health['bot_id']}")
        else:
            print("❌ Firebase连接测试失败")
            print("   请检查服务账号密钥和项目ID")
        
        return health['is_connected']
        
    except ImportError as e:
        print(f"❌ 导入Firebase模块失败: {e}")
        print("   请确保已安装依赖: pip install firebase-admin google-cloud-firestore")
        return False
    except Exception as e:
        print(f"❌ Firebase连接测试失败: {e}")
        return False

def create_deployment_script():
    """创建部署脚本"""
    print("\n📋 步骤5: 创建部署脚本")
    print("-" * 40)
    
    script_content = """#!/bin/bash
# Firebase云存储部署脚本

echo "🚀 开始部署CSBYBot到Render..."

# 检查依赖
echo "📦 检查Python依赖..."
pip install -r requirements.txt

# 测试Firebase连接
echo "🔥 测试Firebase连接..."
python firebase_setup_tool.py --test-only

if [ $? -eq 0 ]; then
    echo "✅ Firebase连接测试通过"
else
    echo "❌ Firebase连接测试失败，请检查配置"
    exit 1
fi

# 启动机器人
echo "🤖 启动机器人..."
python csmain.py

echo "🎉 部署完成!"
"""
    
    script_file = Path('deploy_firebase.sh')
    with open(script_file, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # 设置执行权限
    script_file.chmod(0o755)
    
    print(f"✅ 部署脚本已创建: {script_file.absolute()}")

def main():
    """主函数"""
    print_banner()
    
    # 检查是否已安装依赖
    try:
        import firebase_admin
        print("✅ Firebase依赖已安装")
    except ImportError:
        print("❌ Firebase依赖未安装")
        print("请运行: pip install firebase-admin google-cloud-firestore")
        print()
        return
    
    # 获取Firebase凭据
    credentials = get_firebase_credentials()
    if not credentials:
        print("\n⚠️  请手动设置环境变量后重新运行此工具")
        return
    
    project_id = credentials['project_id']
    
    # 创建环境变量文件
    env_file = create_env_file(credentials, project_id)
    
    # 创建Render配置指南
    create_render_env_guide()
    
    # 测试Firebase连接
    connection_success = test_firebase_connection(credentials, project_id)
    
    # 创建部署脚本
    create_deployment_script()
    
    # 总结
    print("\n" + "=" * 60)
    print("🎉 Firebase设置完成!")
    print("=" * 60)
    print()
    print("📋 下一步操作:")
    print("1. 检查并修改 .env 文件中的机器人配置")
    print("2. 在Render控制台中设置环境变量")
    print("3. 运行: python firebase_setup_tool.py --test-only 测试连接")
    print("4. 部署到Render: ./deploy_firebase.sh")
    print()
    print("📚 相关文件:")
    print(f"   - 环境变量: {env_file.absolute()}")
    print("   - Render配置指南: RENDER_ENV_SETUP.md")
    print("   - 部署脚本: deploy_firebase.sh")
    print()
    print("🔗 帮助文档:")
    print("   - Firebase控制台: https://console.firebase.google.com/")
    print("   - Render文档: https://render.com/docs")

if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--test-only":
        # 仅测试连接
        print("🧪 仅测试Firebase连接...")
        credentials = os.getenv('FIREBASE_CREDENTIALS')
        project_id = os.getenv('FIREBASE_PROJECT_ID')
        
        if credentials and project_id:
            try:
                cred_dict = json.loads(credentials)
                test_firebase_connection(cred_dict, project_id)
            except Exception as e:
                print(f"❌ 测试失败: {e}")
        else:
            print("❌ 未找到Firebase环境变量")
    else:
        # 完整设置流程
        main()
