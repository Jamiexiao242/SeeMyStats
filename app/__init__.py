from flask import Flask
import os
from flask_cors import CORS

def create_app(test_config=None):
    """创建并配置Flask应用"""
    app = Flask(__name__, instance_relative_config=True)
    CORS(app)  # 添加CORS支持，允许跨域请求
    app.config.from_mapping(
        SECRET_KEY='dev',
        UPLOAD_FOLDER=os.path.join(app.instance_path, 'uploads'),
        MAX_CONTENT_LENGTH=1024 * 1024 * 1024  # 1GB limit
    )

    if test_config is None:
        # 加载实例配置（如果存在）
        app.config.from_pyfile('config.py', silent=True)
    else:
        # 加载测试配置
        app.config.from_mapping(test_config)

    # 确保实例文件夹存在
    try:
        os.makedirs(app.instance_path)
        os.makedirs(app.config['UPLOAD_FOLDER'])
    except OSError:
        pass

    # 注册蓝图
    from app.components import dashboard, upload, analysis
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(upload.bp)
    app.register_blueprint(analysis.bp)
    app.add_url_rule('/status', view_func=upload.status)
    
    # 设置主页路由
    from flask import redirect, url_for
    @app.route('/')
    def index():
        return redirect(url_for('upload.upload_file'))
    
    return app 
