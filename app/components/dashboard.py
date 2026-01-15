from flask import (
    Blueprint, flash, g, redirect, render_template, request, 
    session, url_for, jsonify
)
import os
import pandas as pd
from app.utils.health_parser import HealthDataParser
from app.utils.visualization import HealthDataVisualizer
from app.utils.dashboard_cache import load_dashboard_cache, save_dashboard_cache

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

def build_dashboard_payload(parser):
    visualizer = HealthDataVisualizer(parser)
    stats = {}

    heart_rate_stats = parser.get_heart_rate_stats()
    if heart_rate_stats:
        stats['heart_rate'] = heart_rate_stats

    daily_steps = parser.get_daily_step_count()
    if not daily_steps.empty:
        daily_steps['步数'] = pd.to_numeric(daily_steps['步数'], errors='coerce')
        daily_steps = daily_steps.dropna(subset=['步数'])
        if not daily_steps.empty:
            total_steps = float(daily_steps['步数'].sum())
            avg_steps = float(daily_steps['步数'].mean())
            stats['steps'] = {
                '总步数': round(total_steps, 0),
                '平均每日步数': round(avg_steps, 0)
            }

    sleep_data = parser.get_sleep_duration_daily()
    if not sleep_data.empty:
        sleep_data['睡眠时长(小时)'] = pd.to_numeric(
            sleep_data['睡眠时长(小时)'],
            errors='coerce'
        )
        sleep_data = sleep_data.dropna(subset=['睡眠时长(小时)'])
        if not sleep_data.empty:
            avg_sleep = float(sleep_data['睡眠时长(小时)'].mean())
            stats['sleep'] = {
                '平均睡眠时长': round(avg_sleep, 1)
            }

    stress_data = parser.get_stress_indicators()
    if not stress_data.empty and '压力指数' in stress_data.columns:
        stress_data['压力指数'] = pd.to_numeric(
            stress_data['压力指数'],
            errors='coerce'
        )
        stress_data = stress_data.dropna(subset=['压力指数'])
        if not stress_data.empty:
            avg_stress = float(stress_data['压力指数'].mean())
            stats['stress'] = {
                '平均压力指数': round(avg_stress, 1)
            }

    dashboard_chart = visualizer.create_health_dashboard()
    data_types = parser.get_all_data_types()

    return stats, dashboard_chart, data_types

def initialize_parser():
    """初始化解析器并加载数据"""
    parser = HealthDataParser()
    
    # 检查是否有已解析的数据文件
    data_file_path = session.get('data_file_path')
    data_dir_path = session.get('data_dir_path')
    
    if data_file_path and os.path.exists(data_file_path):
        # 如果有XML文件路径，直接解析
        if not parser.parse_xml(data_file_path):
            raise Exception("Error loading data file.")
    elif data_dir_path and os.path.exists(data_dir_path):
        # 如果有目录路径，解析整个目录
        if not parser.parse_directory(data_dir_path):
            raise Exception("Error loading data directory.")
    else:
        # 如果没有可用数据
        return None
    
    return parser

@bp.route('', methods=('GET',))
def index():
    """显示健康数据仪表板"""
    
    # 检查是否有已解析的数据文件或目录
    data_file_path = session.get('data_file_path')
    data_dir_path = session.get('data_dir_path')
    
    if not data_file_path and not data_dir_path:
        # 如果没有已解析的数据，显示首页
        return render_template('index.html', has_data=False)
    
    source_path = data_file_path or data_dir_path

    cached_payload = None
    if source_path:
        cached_payload = load_dashboard_cache(source_path)

    if cached_payload:
        return render_template(
            'dashboard.html',
            has_data=True,
            stats=cached_payload.get('stats', {}),
            dashboard_chart=cached_payload.get('dashboard_chart'),
            data_types=cached_payload.get('data_types', [])
        )

    try:
        # 初始化解析器并加载数据
        parser = initialize_parser()
        if not parser:
            flash('No valid health data found.')
            return render_template('index.html', has_data=False)

        stats, dashboard_chart, data_types = build_dashboard_payload(parser)
        parser.clean_up()

        if source_path:
            save_dashboard_cache(source_path, stats, dashboard_chart, data_types)

        return render_template(
            'dashboard.html',
            has_data=True,
            stats=stats,
            dashboard_chart=dashboard_chart,
            data_types=data_types
        )
    
    except Exception as e:
        flash(f'Error generating dashboard: {str(e)}')
        return render_template('index.html', has_data=False)

@bp.route('/clear', methods=('GET',))
def clear_data():
    """清除会话中的数据"""
    session.pop('data_file_path', None)
    session.pop('data_dir_path', None)
    flash('Data cleared.')
    return redirect(url_for('dashboard.index'))

@bp.route('/chart/<chart_type>', methods=('GET',))
def get_chart(chart_type):
    """获取指定类型的图表"""
    try:
        parser = initialize_parser()
        if not parser:
            return {"error": "No data available."}
        
        visualizer = HealthDataVisualizer(parser)
        
        if chart_type == 'heart_rate':
            chart = visualizer.plot_heart_rate_over_time()
            return chart if chart else {"error": "No heart rate data available."}
        elif chart_type == 'steps':
            chart = visualizer.plot_daily_steps()
            return chart if chart else {"error": "No step data available."}
        elif chart_type == 'sleep':
            chart = visualizer.plot_sleep_duration()
            return chart if chart else {"error": "No sleep data available."}
        elif chart_type == 'stress':
            # 获取压力指标图表
            stress_data = parser.get_stress_indicators()
            if stress_data.empty or '压力指数' not in stress_data.columns:
                return {"error": "No stress data available."}
            chart = visualizer.plot_stress_indicators()
            return chart if chart else {"error": "No stress data available."}
        elif chart_type == 'dashboard':
            chart = visualizer.create_health_dashboard()
            return chart
        else:
            return {"error": "Invalid chart type."}
    except Exception as e:
        print(f"Error fetching chart: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)} 
