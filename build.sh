#!/bin/bash
echo "🔧 开始安装依赖..."

# 升级pip
python -m pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt

# 验证安装
python -c "import pyrogram; print(f'✅ pyrogram {pyrogram.__version__} 安装成功')"
python -c "import tgcrypto; print(f'✅ tgcrypto {tgcrypto.__version__} 安装成功')"
python -c "import dotenv; print(f'✅ python-dotenv 安装成功')"

echo "🎉 依赖安装完成！"
