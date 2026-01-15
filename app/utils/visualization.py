import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import traceback
import datetime

class HealthDataVisualizer:
    """Apple健康数据可视化类"""
    
    def __init__(self, parser):
        """
        初始化可视化器
        
        参数:
            parser: HealthDataParser实例，用于获取健康数据
        """
        self.parser = parser
    
    def plot_daily_steps(self):
        """绘制每日步数图表"""
        daily_steps = self.parser.get_daily_step_count()
        if daily_steps.empty:
            return None
        
        fig = px.bar(
            daily_steps, 
            x='日期', 
            y='步数',
            title='Daily Steps',
            labels={'日期': 'Date', '步数': 'Steps'},
            color_discrete_sequence=['#1f77b4']
        )
        
        # 添加平均线
        avg_steps = daily_steps['步数'].mean()
        fig.add_hline(
            y=avg_steps,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Average: {avg_steps:.0f} steps",
            annotation_position="top right"
        )
        
        # 设置布局
        fig.update_layout(
            xaxis_title='Date',
            yaxis_title='Steps',
            hovermode='x unified',
            height=400
        )
        
        return json.loads(fig.to_json())
    
    def plot_heart_rate_over_time(self):
        """绘制心率随时间变化图表"""
        hr_data = self.parser.get_heart_rate_data()
        if hr_data.empty:
            return None
        
        # 确保value列是数值类型
        hr_data['value'] = pd.to_numeric(hr_data['value'], errors='coerce')
        
        # 重采样为小时数据点以减少数据量
        hr_data.set_index('startDate', inplace=True)
        hr_hourly = hr_data.resample('H').mean().reset_index()
        
        # 创建图表
        fig = px.line(
            hr_hourly, 
            x='startDate', 
            y='value',
            title='Heart Rate Trend',
            labels={'startDate': 'Time', 'value': 'Heart Rate (bpm)'},
            color_discrete_sequence=['#ff7f0e']
        )
        
        # 添加心率区间
        fig.add_hrect(
            y0=100, y1=max(hr_hourly['value'].max(), 100),
            fillcolor="red", opacity=0.1,
            layer="below", line_width=0,
            annotation_text="High heart rate zone",
            annotation_position="top right"
        )
        
        fig.add_hrect(
            y0=60, y1=100,
            fillcolor="green", opacity=0.1,
            layer="below", line_width=0,
            annotation_text="Normal heart rate zone",
            annotation_position="top left"
        )
        
        fig.add_hrect(
            y0=min(hr_hourly['value'].min(), 60), y1=60,
            fillcolor="blue", opacity=0.1,
            layer="below", line_width=0,
            annotation_text="Low heart rate zone",
            annotation_position="bottom left"
        )
        
        # 设置布局
        fig.update_layout(
            xaxis_title='Time',
            yaxis_title='Heart Rate (bpm)',
            hovermode='x unified',
            height=400
        )
        
        return json.loads(fig.to_json())
    
    def plot_sleep_duration(self):
        """绘制睡眠时长图表"""
        sleep_data = self.parser.get_sleep_duration_daily()
        if sleep_data.empty:
            return None
        
        # 创建图表
        fig = px.bar(
            sleep_data, 
            x='日期', 
            y='睡眠时长(小时)',
            title='Daily Sleep Duration',
            labels={'日期': 'Date', '睡眠时长(小时)': 'Sleep Duration (hours)'},
            color_discrete_sequence=['#2ca02c']
        )
        
        # 添加推荐睡眠时长线
        fig.add_hline(
            y=8,
            line_dash="dash",
            line_color="red",
            annotation_text="Recommended sleep: 8 hours",
            annotation_position="top right"
        )
        
        # 设置布局
        fig.update_layout(
            xaxis_title='Date',
            yaxis_title='Sleep Duration (hours)',
            hovermode='x unified',
            height=400
        )
        
        return json.loads(fig.to_json())
    
    def plot_stress_indicators(self):
        """绘制压力指标图表"""
        stress_data = self.parser.get_stress_indicators()
        if stress_data.empty:
            return None
        
        # 创建子图
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("Heart Rate Variability (Stress)", "Daily Stress Index"),
            vertical_spacing=0.15
        )
        
        # 添加心率波动图
        fig.add_trace(
            go.Scatter(
                x=stress_data['日期'], 
                y=stress_data['心率波动'],
                mode='lines+markers',
                name='HRV',
                line=dict(color='#d62728')
            ),
            row=1, col=1
        )
        
        # 添加压力指数图
        fig.add_trace(
            go.Bar(
                x=stress_data['日期'], 
                y=stress_data['压力指数'],
                name='Stress Index',
                marker_color='#9467bd'
            ),
            row=2, col=1
        )
        
        # 设置布局
        fig.update_layout(
            height=600,
            hovermode='x unified',
            showlegend=False
        )
        
        fig.update_xaxes(title_text='Date', row=2, col=1)
        fig.update_yaxes(title_text='Heart Rate Std Dev', row=1, col=1)
        fig.update_yaxes(title_text='Stress Index', row=2, col=1)
        
        return json.loads(fig.to_json())
    
    def create_health_dashboard(self, days=30):
        """创建健康数据仪表板"""
        try:
            print("Starting health dashboard build...")
            
            # 获取步数数据
            steps_data = self.parser.get_step_count_data()
            print(f"Steps data type: {type(steps_data)}")
            if not steps_data.empty:
                print(f"Steps data columns: {steps_data.columns.tolist()}")
                print(f"Steps value column type: {type(steps_data['value'].iloc[0]) if 'value' in steps_data.columns and not steps_data.empty else 'N/A'}")
            
            steps_df = self._prepare_steps_chart_data(steps_data, days)
            
            # 获取心率数据
            heart_rate_data = self.parser.get_heart_rate_data()
            print(f"Heart rate data type: {type(heart_rate_data)}")
            if not heart_rate_data.empty:
                print(f"Heart rate data columns: {heart_rate_data.columns.tolist()}")
                print(f"Heart rate value column type: {type(heart_rate_data['value'].iloc[0]) if 'value' in heart_rate_data.columns and not heart_rate_data.empty else 'N/A'}")
            
            hr_df = self._prepare_heart_rate_chart_data(heart_rate_data, days)
            print(f"Processed heart rate data type: {type(hr_df)}")
            if not hr_df.empty:
                print(f"Processed heart rate data columns: {hr_df.columns.tolist()}")
                print(f"Processed heart rate value column type: {type(hr_df['value'].iloc[0]) if 'value' in hr_df.columns and not hr_df.empty else 'N/A'}")
            
            # 获取睡眠数据
            sleep_data = self.parser.get_sleep_analysis_data()
            print(f"Sleep data type: {type(sleep_data)}")
            if not sleep_data.empty:
                print(f"Sleep data columns: {sleep_data.columns.tolist()}")
                if 'duration' in sleep_data.columns:
                    print(f"Sleep duration column type: {type(sleep_data['duration'].iloc[0])}")
            
            # 直接使用duration列，duration列已经在sleep_analysis_data方法中计算好了
            if not sleep_data.empty and 'duration' in sleep_data.columns:
                sleep_df = self._prepare_sleep_chart_data(sleep_data, days)
                print(f"Processed sleep data type: {type(sleep_df)}")
                if not sleep_df.empty:
                    print(f"Processed sleep data columns: {sleep_df.columns.tolist()}")
                    print(f"Processed sleep duration column type: {type(sleep_df['duration'].iloc[0]) if 'duration' in sleep_df.columns and not sleep_df.empty else 'N/A'}")
            else:
                sleep_df = pd.DataFrame()
            
            # 准备返回的完整图表数据
            chart_data = {}
            has_any_data = False
            
            # 创建各个图表并存储
            try:
                print("Creating steps chart...")
                steps_chart = None
                if not steps_df.empty:
                    steps_chart = self._create_steps_chart(steps_df)
                    if steps_chart and 'data' in steps_chart and len(steps_chart['data']) > 0:
                        chart_data['steps'] = steps_chart
                        has_any_data = True
                        print(f"Steps chart created with {len(steps_chart['data'])} traces")
                    else:
                        print("Steps chart failed or has no valid data")
                else:
                    print("Steps data is empty; skipping chart")
            except Exception as e:
                print(f"Error creating steps chart: {str(e)}")
                traceback.print_exc()

            try:
                print("Creating heart rate chart...")
                hr_chart = None
                if not hr_df.empty:
                    hr_chart = self._create_heart_rate_chart(hr_df)
                    if hr_chart and 'data' in hr_chart and len(hr_chart['data']) > 0:
                        chart_data['heart_rate'] = hr_chart
                        has_any_data = True
                        print(f"Heart rate chart created with {len(hr_chart['data'])} traces")
                    else:
                        print("Heart rate chart failed or has no valid data")
                else:
                    print("Heart rate data is empty; skipping chart")
            except Exception as e:
                print(f"Error creating heart rate chart: {str(e)}")
                traceback.print_exc()

            try:
                print("Creating sleep chart...")
                sleep_chart = None
                if not sleep_df.empty and 'duration' in sleep_df.columns:
                    sleep_chart = self._create_sleep_chart(sleep_df)
                    if sleep_chart and 'data' in sleep_chart and len(sleep_chart['data']) > 0:
                        chart_data['sleep'] = sleep_chart
                        has_any_data = True
                        print(f"Sleep chart created with {len(sleep_chart['data'])} traces")
                    else:
                        print("Sleep chart failed or has no valid data")
                else:
                    print("Sleep data is empty or missing duration; skipping chart")
            except Exception as e:
                print(f"Error creating sleep chart: {str(e)}")
                traceback.print_exc()

            # 检查是否有任何有效图表
            if not has_any_data:
                print("No valid data to build the dashboard")
                # 创建一个默认的空仪表板，但带有提示信息
                empty_chart = {
                    "data": [
                        {
                            "type": "scatter",
                            "x": [],
                            "y": [],
                            "mode": "text",
                            "text": ["No health data available"],
                            "textposition": "middle center"
                        }
                    ],
                    "layout": {
                        "title": {"text": "No health data available"},
                        "height": 500,
                        "xaxis": {"visible": False},
                        "yaxis": {"visible": False}
                    }
                }
                return empty_chart
            
            # 创建一个综合仪表板
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=(
                    "Daily Steps" if 'steps' in chart_data else "",
                    "Heart Rate Trend" if 'heart_rate' in chart_data else "",
                    "Sleep Duration" if 'sleep' in chart_data else "",
                    ""
                ),
                specs=[
                    [{"type": "scatter"}, {"type": "scatter"}],
                    [{"type": "scatter"}, {"type": "scatter"}]
                ],
                vertical_spacing=0.12,
                horizontal_spacing=0.07
            )
            
            # 填充仪表板
            trace_count = 0
            
            # 添加步数图表
            if 'steps' in chart_data and 'data' in chart_data['steps']:
                for trace in chart_data['steps']['data']:
                    if trace:
                        fig.add_trace(trace, row=1, col=1)
                        trace_count += 1
                        
            # 添加心率图表
            if 'heart_rate' in chart_data and 'data' in chart_data['heart_rate']:
                for trace in chart_data['heart_rate']['data']:
                    if trace:
                        fig.add_trace(trace, row=1, col=2)
                        trace_count += 1
                        
            # 添加睡眠图表
            if 'sleep' in chart_data and 'data' in chart_data['sleep']:
                for trace in chart_data['sleep']['data']:
                    if trace:
                        fig.add_trace(trace, row=2, col=1)
                        trace_count += 1
                        
            # 设置布局
            fig.update_layout(
                title_text="Health Data Summary",
                height=800,
                showlegend=False
            )
            
            print(f"Dashboard created with {trace_count} traces")
            
            # 检查是否有任何trace被添加
            if trace_count == 0:
                print("Warning: dashboard has no traces")
                # 创建一个默认的空仪表板，但带有提示信息
                empty_chart = {
                    "data": [
                        {
                            "type": "scatter",
                            "x": [],
                            "y": [],
                            "mode": "text",
                            "text": ["No health data available"],
                            "textposition": "middle center"
                        }
                    ],
                    "layout": {
                        "title": {"text": "No health data available"},
                        "height": 500,
                        "xaxis": {"visible": False},
                        "yaxis": {"visible": False}
                    }
                }
                return empty_chart
                
            dashboard_json = json.loads(fig.to_json())
            print("Dashboard converted to JSON")
            return dashboard_json
            
        except Exception as e:
            print(f"Error creating health dashboard: {str(e)}")
            traceback.print_exc()
            # 返回错误信息
            return {
                "data": [
                    {
                        "type": "scatter",
                        "x": [],
                        "y": [],
                        "mode": "text",
                        "text": [f"Error creating dashboard: {str(e)}"],
                        "textposition": "middle center"
                    }
                ],
                "layout": {
                    "title": {"text": "Dashboard Creation Failed"},
                    "height": 500,
                    "xaxis": {"visible": False},
                    "yaxis": {"visible": False}
                }
            }
    
    def _prepare_steps_chart_data(self, steps_data, days=30):
        """准备步数图表数据"""
        try:
            print("Preparing steps chart data...")
            if steps_data.empty:
                print("Steps data is empty")
                return pd.DataFrame()
            
            print(f"Steps data columns: {steps_data.columns.tolist()}")
            
            # 提取日期部分
            steps_data['日期'] = steps_data['startDate'].dt.date
            print(f"Columns after adding date: {steps_data.columns.tolist()}")
            
            # 按日期分组并计算总步数
            daily_steps = steps_data.groupby('日期').agg({'value': 'sum'}).reset_index()
            print(f"Columns after daily grouping: {daily_steps.columns.tolist()}")
            
            # 确保value列是数值类型
            daily_steps['value'] = pd.to_numeric(daily_steps['value'], errors='coerce')
            daily_steps = daily_steps.dropna(subset=['value'])
            if not daily_steps.empty:
                print(f"Steps value column type after coercion: {type(daily_steps['value'].iloc[0])}")
            
            # 只保留最近的N天数据
            cutoff_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).date()
            recent_steps = daily_steps[daily_steps['日期'] >= cutoff_date]
            
            # 按日期排序
            recent_steps = recent_steps.sort_values('日期')
            
            # 转换日期为字符串，以便JSON序列化
            recent_steps['日期'] = recent_steps['日期'].astype(str)
            print(f"Processed steps data shape: {recent_steps.shape}")
            
            return recent_steps
        except Exception as e:
            print(f"Error preparing steps chart data: {str(e)}")
            traceback.print_exc()
            return pd.DataFrame()

    def _prepare_heart_rate_chart_data(self, heart_rate_data, days=30):
        """准备心率图表数据"""
        try:
            print("Preparing heart rate chart data...")
            if heart_rate_data.empty:
                print("Heart rate data is empty")
                return pd.DataFrame()
            
            print(f"Raw heart rate data columns: {heart_rate_data.columns.tolist()}")
            if 'value' in heart_rate_data.columns:
                print(f"Heart rate value column type: {type(heart_rate_data['value'].iloc[0]) if not heart_rate_data.empty else 'N/A'}")
                
                # 确保value列是数值类型
                heart_rate_data['value'] = pd.to_numeric(heart_rate_data['value'], errors='coerce')
                # 过滤掉NaN值
                heart_rate_data = heart_rate_data.dropna(subset=['value'])
                if not heart_rate_data.empty:
                    print(f"Heart rate value column type after coercion: {type(heart_rate_data['value'].iloc[0])}")
            
            # 重采样为小时数据点以减少数据量
            heart_rate_data.set_index('startDate', inplace=True)
            hr_hourly = heart_rate_data.resample('H').mean().reset_index()
            print(f"Resampled heart rate data columns: {hr_hourly.columns.tolist()}")
            
            # 提取日期部分
            hr_hourly['日期'] = hr_hourly['startDate'].dt.date
            
            # 只保留最近的N天数据
            cutoff_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).date()
            recent_hr = hr_hourly[hr_hourly['日期'] >= cutoff_date]
            
            # 按日期排序
            recent_hr = recent_hr.sort_values('日期')
            
            # 转换日期为字符串，以便JSON序列化
            recent_hr['日期'] = recent_hr['日期'].astype(str)
            print(f"Processed heart rate data shape: {recent_hr.shape}")
            if 'value' in recent_hr.columns and not recent_hr.empty:
                print(f"Processed heart rate value column type: {type(recent_hr['value'].iloc[0])}")
                print(f"First heart rate values: {recent_hr['value'].head().tolist()}")
            
            return recent_hr
        except Exception as e:
            print(f"Error preparing heart rate chart data: {str(e)}")
            traceback.print_exc()
            return pd.DataFrame()

    def _prepare_sleep_chart_data(self, sleep_data, days=30):
        """准备睡眠图表数据"""
        try:
            print("Preparing sleep chart data...")
            if sleep_data.empty:
                print("Sleep data is empty")
                return pd.DataFrame()
            
            print(f"Raw sleep data columns: {sleep_data.columns.tolist()}")
            if 'duration' in sleep_data.columns:
                print(f"Sleep duration column type: {type(sleep_data['duration'].iloc[0]) if not sleep_data.empty else 'N/A'}")
                # 确保duration列是数值类型
                sleep_data['duration'] = pd.to_numeric(sleep_data['duration'], errors='coerce')
                # 过滤掉NaN值
                sleep_data = sleep_data.dropna(subset=['duration'])
                if not sleep_data.empty:
                    print(f"Sleep duration column type after coercion: {type(sleep_data['duration'].iloc[0])}")
                    print(f"First sleep duration values: {sleep_data['duration'].head().tolist()}")
            
            # 提取日期部分 - 添加这一步，从startDate创建日期列
            if 'startDate' in sleep_data.columns and '日期' not in sleep_data.columns:
                print("Creating date column from startDate")
                sleep_data['日期'] = sleep_data['startDate'].dt.date
            
            # 只保留最近的N天数据
            cutoff_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).date()
            
            # 确保日期列存在
            if '日期' not in sleep_data.columns:
                print("Warning: sleep data missing date column; returning all data")
                recent_sleep = sleep_data.copy()
            else:
                recent_sleep = sleep_data[sleep_data['日期'] >= cutoff_date]
            
            # 按日期排序
            if '日期' in recent_sleep.columns:
                recent_sleep = recent_sleep.sort_values('日期')
                
                # 转换日期为字符串，以便JSON序列化
                recent_sleep['日期'] = recent_sleep['日期'].astype(str)
            else:
                # 如果没有日期列，尝试按startDate排序
                if 'startDate' in recent_sleep.columns:
                    recent_sleep = recent_sleep.sort_values('startDate')
                    
                    # 创建一个日期列用于显示
                    recent_sleep['日期'] = recent_sleep['startDate'].dt.date.astype(str)
            
            print(f"Processed sleep data shape: {recent_sleep.shape}")
            
            return recent_sleep
        except Exception as e:
            print(f"Error preparing sleep chart data: {str(e)}")
            traceback.print_exc()
            return pd.DataFrame()

    def _create_steps_chart(self, steps_data):
        """创建步数图表"""
        try:
            print("Starting steps chart creation...")
            if steps_data.empty:
                return None
            
            print(f"Steps data columns: {steps_data.columns.tolist()}")
            print(f"Steps value column type: {type(steps_data['value'].iloc[0]) if 'value' in steps_data.columns and not steps_data.empty else 'N/A'}")
            
            # 创建一个副本避免修改原始数据
            steps_chart_data = steps_data.copy()
            
            # 确保value列是数值类型
            if 'value' in steps_chart_data.columns:
                steps_chart_data['value'] = pd.to_numeric(steps_chart_data['value'], errors='coerce')
                steps_chart_data = steps_chart_data.dropna(subset=['value'])
                if not steps_chart_data.empty:
                    print(f"Steps value column type after conversion: {type(steps_chart_data['value'].iloc[0])}")
                    print(f"First step values: {steps_chart_data['value'].head().tolist()}")
            
            if steps_chart_data.empty:
                print("No data after conversion; cannot create chart")
                return None
            
            fig = px.bar(
                steps_chart_data, 
                x='日期', 
                y='value',
                title='Daily Steps',
                labels={'日期': 'Date', 'value': 'Steps'},
                color_discrete_sequence=['#1f77b4']
            )
            
            # 添加平均线
            avg_steps = float(steps_chart_data['value'].mean())
            print(f"Average steps: {avg_steps}, type: {type(avg_steps)}")
            
            fig.add_hline(
                y=avg_steps,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Average: {avg_steps:.0f} steps",
                annotation_position="top right"
            )
            
            # 设置布局
            fig.update_layout(
                xaxis_title='Date',
                yaxis_title='Steps',
                hovermode='x unified',
                height=400
            )
            
            print("Steps chart created")
            return json.loads(fig.to_json())
        except Exception as e:
            print(f"Error creating steps chart: {str(e)}")
            traceback.print_exc()
            return None

    def _create_heart_rate_chart(self, hr_data):
        """创建心率图表"""
        try:
            print("Starting heart rate chart creation...")
            if hr_data.empty:
                return None
            
            print(f"Heart rate data columns: {hr_data.columns.tolist()}")
            print(f"Heart rate value column type: {type(hr_data['value'].iloc[0]) if 'value' in hr_data.columns and not hr_data.empty else 'N/A'}")
            
            # 创建一个副本避免修改原始数据
            hr_chart_data = hr_data.copy()
            
            # 确保value列是数值类型
            if 'value' in hr_chart_data.columns:
                hr_chart_data['value'] = pd.to_numeric(hr_chart_data['value'], errors='coerce')
                hr_chart_data = hr_chart_data.dropna(subset=['value'])
                if not hr_chart_data.empty:
                    print(f"Heart rate value column type after conversion: {type(hr_chart_data['value'].iloc[0])}")
                    print(f"First heart rate values: {hr_chart_data['value'].head().tolist()}")
            
            if hr_chart_data.empty:
                print("No data after conversion; cannot create chart")
                return None
            
            fig = px.line(
                hr_chart_data, 
                x='日期', 
                y='value',
                title='Heart Rate Trend',
                labels={'日期': 'Date', 'value': 'Heart Rate (bpm)'},
                color_discrete_sequence=['#ff7f0e']
            )
            
            # 添加心率区间
            max_value = float(hr_chart_data['value'].max())
            min_value = float(hr_chart_data['value'].min())
            print(f"Max heart rate: {max_value}, type: {type(max_value)}")
            print(f"Min heart rate: {min_value}, type: {type(min_value)}")
            
            fig.add_hrect(
                y0=100, y1=max(max_value, 100),
                fillcolor="red", opacity=0.1,
                layer="below", line_width=0,
                annotation_text="High heart rate zone",
                annotation_position="top right"
            )
            
            fig.add_hrect(
                y0=60, y1=100,
                fillcolor="green", opacity=0.1,
                layer="below", line_width=0,
                annotation_text="Normal heart rate zone",
                annotation_position="top left"
            )
            
            fig.add_hrect(
                y0=min(min_value, 60), y1=60,
                fillcolor="blue", opacity=0.1,
                layer="below", line_width=0,
                annotation_text="Low heart rate zone",
                annotation_position="bottom left"
            )
            
            # 设置布局
            fig.update_layout(
                xaxis_title='Date',
                yaxis_title='Heart Rate (bpm)',
                hovermode='x unified',
                height=400
            )
            
            print("Heart rate chart created")
            return json.loads(fig.to_json())
        except Exception as e:
            print(f"Error creating heart rate chart: {str(e)}")
            traceback.print_exc()
            return None

    def _create_sleep_chart(self, sleep_data):
        """创建睡眠图表"""
        try:
            print("Starting sleep chart creation...")
            if sleep_data.empty:
                return None
            
            print(f"Sleep data columns: {sleep_data.columns.tolist()}")
            print(f"Sleep duration column type: {type(sleep_data['duration'].iloc[0]) if 'duration' in sleep_data.columns and not sleep_data.empty else 'N/A'}")
            
            # 创建一个副本避免修改原始数据
            sleep_chart_data = sleep_data.copy()
            
            # 确保duration列是数值类型
            if 'duration' in sleep_chart_data.columns:
                sleep_chart_data['duration'] = pd.to_numeric(sleep_chart_data['duration'], errors='coerce')
                sleep_chart_data = sleep_chart_data.dropna(subset=['duration'])
                if not sleep_chart_data.empty:
                    print(f"Sleep duration column type after conversion: {type(sleep_chart_data['duration'].iloc[0])}")
                    print(f"First sleep duration values: {sleep_chart_data['duration'].head().tolist()}")
            
            if sleep_chart_data.empty:
                print("No data after conversion; cannot create chart")
                return None
            
            # 创建图表
            fig = go.Figure()
            
            # 添加睡眠时间柱状图
            fig.add_trace(go.Bar(
                x=sleep_chart_data['日期'],
                y=sleep_chart_data['duration'],  # 这里使用duration而不是value
                marker_color='skyblue',
                name='Sleep Duration (hours)'
            ))
            
            # 设置图表标题和轴标签
            fig.update_layout(
                title='Daily Sleep Duration',
                xaxis_title='Date',
                yaxis_title='Sleep Duration (hours)',
                template='plotly_white',
                margin=dict(l=0, r=0, t=30, b=0),
                height=300
            )
            
            print("Sleep chart created")
            # 与其他图表保持一致，返回JSON而不是HTML
            return json.loads(fig.to_json())
        except Exception as e:
            print(f"Error creating sleep chart: {str(e)}")
            traceback.print_exc()
            return None
