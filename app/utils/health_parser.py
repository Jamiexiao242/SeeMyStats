import os
import pandas as pd
import numpy as np
import zipfile
import xml.etree.ElementTree as ET
import json
import glob
from datetime import datetime, timezone
import shutil
import csv
import traceback
import pickle

CACHE_FILENAME = "health_cache.pkl"
CACHE_VERSION = 1
MEMORY_CACHE_LIMIT = 1
MEMORY_CACHE = {}
MEMORY_CACHE_ORDER = []

def _store_memory_cache(cache_path, payload):
    MEMORY_CACHE[cache_path] = payload
    if cache_path in MEMORY_CACHE_ORDER:
        MEMORY_CACHE_ORDER.remove(cache_path)
    MEMORY_CACHE_ORDER.append(cache_path)
    while len(MEMORY_CACHE_ORDER) > MEMORY_CACHE_LIMIT:
        old_path = MEMORY_CACHE_ORDER.pop(0)
        if old_path != cache_path:
            MEMORY_CACHE.pop(old_path, None)

class HealthDataParser:
    """Apple健康数据解析类"""
    
    def __init__(self):
        """初始化解析器"""
        self.records = []  # 所有健康记录
        self.record_types = {}  # 记录类型映射
        self.xml_root = None  # XML根元素
        self.temp_dirs = []  # 临时目录列表，用于清理
    
    def clean_up(self):
        """清理临时文件和目录"""
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        self.temp_dirs = []

    def _cache_path_for_source(self, source_path):
        if os.path.isdir(source_path):
            return os.path.join(source_path, CACHE_FILENAME)
        return os.path.join(os.path.dirname(source_path), CACHE_FILENAME)

    def _get_source_stamp(self, source_path):
        try:
            if os.path.isdir(source_path):
                xml_files = glob.glob(os.path.join(source_path, "**", "export.xml"), recursive=True)
                xml_files.extend(glob.glob(os.path.join(source_path, "**", "輸出.xml"), recursive=True))
                if xml_files:
                    return self._get_source_stamp(xml_files[0])
                stat_info = os.stat(source_path)
                return {
                    "type": "dir",
                    "path": source_path,
                    "mtime": stat_info.st_mtime,
                }

            stat_info = os.stat(source_path)
            return {
                "type": "file",
                "path": source_path,
                "mtime": stat_info.st_mtime,
                "size": stat_info.st_size,
            }
        except OSError:
            return None

    def _load_cache(self, cache_path, source_path):
        if not os.path.exists(cache_path):
            return False

        source_stamp = self._get_source_stamp(source_path)
        if not source_stamp:
            return False

        memory_payload = MEMORY_CACHE.get(cache_path)
        if memory_payload:
            if (
                memory_payload.get("cache_version") == CACHE_VERSION and
                memory_payload.get("source_stamp") == source_stamp
            ):
                self.records = memory_payload.get("records", [])
                self.record_types = memory_payload.get("record_types", {})
                self.xml_root = None
                print(f"Loaded cached health data from memory ({cache_path})")
                return len(self.records) > 0

        try:
            with open(cache_path, 'rb') as cache_file:
                payload = pickle.load(cache_file)
        except Exception:
            return False

        if not isinstance(payload, dict):
            return False

        if payload.get("cache_version") != CACHE_VERSION:
            return False

        if payload.get("source_stamp") != source_stamp:
            return False

        self.records = payload.get("records", [])
        self.record_types = payload.get("record_types", {})
        self.xml_root = None
        _store_memory_cache(cache_path, payload)
        print(f"Loaded cached health data from {cache_path}")
        return len(self.records) > 0

    def _save_cache(self, cache_path, source_path):
        source_stamp = self._get_source_stamp(source_path)
        if not source_stamp:
            return

        payload = {
            "cache_version": CACHE_VERSION,
            "source_stamp": source_stamp,
            "records": self.records,
            "record_types": self.record_types,
        }

        tmp_path = f"{cache_path}.tmp"
        try:
            with open(tmp_path, 'wb') as cache_file:
                pickle.dump(payload, cache_file, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp_path, cache_path)
            _store_memory_cache(cache_path, payload)
            print(f"Saved cache to {cache_path}")
        except Exception as e:
            print(f"Failed to save cache {cache_path}: {str(e)}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
    
    def extract_from_zip(self, zip_path):
        """
        从ZIP文件中提取Apple健康导出的XML文件
        
        参数:
            zip_path: ZIP文件路径
            
        返回:
            提取的XML文件路径或None（如果未找到）
        """
        try:
            # 创建临时目录
            import tempfile
            extract_dir = tempfile.mkdtemp()
            self.temp_dirs.append(extract_dir)
            
            # 提取ZIP文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 查找export.xml或輸出.xml文件
                xml_files = [f for f in zip_ref.namelist() if f.endswith('export.xml') or f.endswith('輸出.xml')]
                
                if not xml_files:
                    print("No export.xml found in the ZIP file")
                    return None
                
                # 提取找到的XML文件
                xml_path = os.path.join(extract_dir, os.path.basename(xml_files[0]))
                for xml_file in xml_files:
                    with open(xml_path, 'wb') as f:
                        f.write(zip_ref.read(xml_file))
                
                return xml_path
        except Exception as e:
            print(f"Error extracting XML from ZIP: {str(e)}")
            traceback.print_exc()
            return None
    
    def parse_xml(self, xml_path, progress_callback=None):
        """
        解析Apple健康导出的XML文件
        
        参数:
            xml_path: XML文件路径
            progress_callback: Optional callback for progress updates.
            
        返回:
            解析是否成功
        """
        try:
            cache_path = self._cache_path_for_source(xml_path)
            if self._load_cache(cache_path, xml_path):
                if progress_callback:
                    progress_callback(95, "Loaded cached data.")
                return True

            # 解析XML文件
            # 注意：Apple健康导出的XML文件可能非常大，使用迭代解析
            print(f"Parsing XML file: {xml_path}")

            total_size = None
            try:
                total_size = os.path.getsize(xml_path)
            except OSError:
                total_size = None

            last_progress = -1
            record_count = 0

            # 使用迭代器解析大型XML文件
            with open(xml_path, 'rb') as xml_file:
                for event, elem in ET.iterparse(xml_file, events=('end',)):
                    if elem.tag == 'Record':
                        # 提取记录属性
                        record = elem.attrib
                        self.records.append(record)
                        
                        # 记录类型
                        record_type = record.get('type')
                        if record_type:
                            if record_type not in self.record_types:
                                self.record_types[record_type] = []
                            self.record_types[record_type].append(record)

                        record_count += 1
                        if progress_callback and total_size and record_count % 5000 == 0:
                            current_pos = xml_file.tell()
                            progress = int((current_pos / total_size) * 90) + 5
                            progress = max(5, min(95, progress))
                            if progress != last_progress:
                                progress_callback(progress, f"Parsing export.xml... {progress}%")
                                last_progress = progress
                    
                    # 清除元素以节省内存
                    elem.clear()
            
            print(f"XML parse complete: {len(self.records)} records, {len(self.record_types)} types")
            self._save_cache(cache_path, xml_path)
            return len(self.records) > 0
        except Exception as e:
            print(f"Error parsing XML file: {str(e)}")
            traceback.print_exc()
            return False
    
    def parse_directory(self, directory_path):
        """
        解析包含Apple健康导出文件的目录
        
        参数:
            directory_path: 目录路径
            
        返回:
            解析是否成功
        """
        try:
            success = False
            parsed_xml = False

            # 查找XML文件
            xml_files = glob.glob(os.path.join(directory_path, "**", "*.xml"), recursive=True)
            export_files = [
                xml_file for xml_file in xml_files
                if os.path.basename(xml_file) in ['export.xml', '輸出.xml']
            ]
            cache_source = export_files[0] if export_files else directory_path
            cache_path = self._cache_path_for_source(cache_source)
            if self._load_cache(cache_path, cache_source):
                return True

            for xml_file in export_files:
                if self.parse_xml(xml_file):
                    success = True
                    parsed_xml = True
                    break
            
            # 如果没有找到XML文件或解析不成功，尝试查找JSON文件
            if not success:
                success = self.parse_json_files(directory_path)
            
            # 如果仍然不成功，尝试查找CSV文件
            if not success:
                success = self.parse_csv_files(directory_path)

            if success and not parsed_xml:
                self._save_cache(cache_path, directory_path)
            
            return success
        except Exception as e:
            print(f"Error parsing directory: {str(e)}")
            traceback.print_exc()
            return False
    
    def parse_json_files(self, directory_path):
        """
        解析目录中的JSON文件
        
        参数:
            directory_path: 目录路径
            
        返回:
            解析是否成功
        """
        try:
            json_files = glob.glob(os.path.join(directory_path, "**", "*.json"), recursive=True)
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # 检查是否是健康记录JSON格式
                        if isinstance(data, list):
                            for record in data:
                                if isinstance(record, dict) and 'type' in record:
                                    self.records.append(record)
                                    
                                    # 记录类型
                                    record_type = record.get('type')
                                    if record_type:
                                        if record_type not in self.record_types:
                                            self.record_types[record_type] = []
                                        self.record_types[record_type].append(record)
                except Exception as e:
                    print(f"Error parsing JSON file {json_file}: {str(e)}")
                    continue
            
            return len(self.records) > 0
        except Exception as e:
            print(f"Error parsing JSON files: {str(e)}")
            traceback.print_exc()
            return False
    
    def parse_csv_files(self, directory_path):
        """
        解析目录中的CSV文件
        
        参数:
            directory_path: 目录路径
            
        返回:
            解析是否成功
        """
        try:
            csv_files = glob.glob(os.path.join(directory_path, "**", "*.csv"), recursive=True)
            for csv_file in csv_files:
                try:
                    # 检测文件编码
                    encoding = 'utf-8'
                    try:
                        with open(csv_file, 'r', encoding='utf-8') as f:
                            f.readline()
                    except UnicodeDecodeError:
                        encoding = 'latin-1'  # 尝试使用其他编码
                    
                    # 读取CSV文件
                    df = pd.read_csv(csv_file, encoding=encoding)
                    
                    # 检查列名以确定这是否是健康数据CSV
                    health_data_columns = ['type', 'startDate', 'endDate', 'value']
                    has_health_columns = any(col in df.columns for col in health_data_columns)
                    
                    if has_health_columns:
                        # 转换为字典记录列表
                        records = df.to_dict('records')
                        
                        for record in records:
                            # 确保记录有type字段
                            if 'type' in record:
                                self.records.append(record)
                                
                                # 记录类型
                                record_type = record.get('type')
                                if record_type:
                                    if record_type not in self.record_types:
                                        self.record_types[record_type] = []
                                    self.record_types[record_type].append(record)
                except Exception as e:
                    print(f"Error parsing CSV file {csv_file}: {str(e)}")
                    continue
            
            return len(self.records) > 0
        except Exception as e:
            print(f"Error parsing CSV files: {str(e)}")
            traceback.print_exc()
            return False
    
    def get_all_data_types(self):
        """获取所有可用的数据类型"""
        return list(self.record_types.keys())
    
    def get_data_by_type(self, data_type):
        """
        获取指定类型的健康数据
        
        参数:
            data_type: Apple Health 中的类型字符串（如 "HKQuantityTypeIdentifierBodyMassIndex"）
            
        返回:
            包含指定类型数据的 DataFrame，如果该类型不存在则返回空的 DataFrame
        """
        try:
            # 检查该类型是否存在
            if data_type not in self.record_types:
                print(f"Data type {data_type} not found")
                return pd.DataFrame()
            
            # 获取该类型的所有记录
            records = self.record_types[data_type]
            
            if not records:
                print(f"Data type {data_type} has no records")
                return pd.DataFrame()
            
            # 将记录列表转换为 DataFrame
            df = pd.DataFrame(records)
            
            # 确保日期列是 datetime 类型
            for col in df.columns:
                if col.lower() in ['startdate', 'enddate', 'date', '日期', 'start', 'end']:
                    try:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                    except:
                        pass
            
            # 按日期排序（如果有合适的日期列）
            date_cols = [col for col in df.columns if col.lower() in ['startdate', 'date', '日期', 'start']]
            if date_cols:
                df = df.sort_values(date_cols[0])
            
            return df
            
        except Exception as e:
            print(f"Error getting data for type {data_type}: {str(e)}")
            traceback.print_exc()
            return pd.DataFrame()
    
    def _safe_date_conversion(self, date_str):
        """
        安全地将日期字符串转换为datetime对象
        
        参数:
            date_str: 日期字符串
            
        返回:
            datetime对象
        """
        try:
            # 检查并处理带有时区信息的日期
            if 'Z' in date_str or '+' in date_str or 'T' in date_str:
                # 尝试多种日期格式
                for fmt in ['%Y-%m-%d %H:%M:%S%z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%SZ', '%Y-%m-%dT%H:%M:%SZ']:
                    try:
                        # 替换Z为+00:00以标准化UTC时区表示
                        if 'Z' in date_str:
                            date_str = date_str.replace('Z', '+00:00')
                        return pd.to_datetime(date_str, format=fmt)
                    except:
                        continue
                
                # 如果以上格式都失败，尝试使用pandas默认解析
                return pd.to_datetime(date_str, utc=True)
            else:
                # 对于没有时区信息的日期，假设为本地时间
                return pd.to_datetime(date_str)
        except Exception as e:
            print(f"Date conversion failed ({date_str}): {str(e)}")
            # 返回当前时间作为后备选项
            return pd.Timestamp.now()
    
    def _extract_date(self, record):
        """
        从记录中提取日期
        
        参数:
            record: 健康记录字典
            
        返回:
            提取的日期或当前日期（如果无法提取）
        """
        date = None
        
        # 尝试不同的日期字段
        date_fields = ['startDate', 'endDate', 'date', '日期', 'Start', 'End']
        for field in date_fields:
            if field in record and record[field]:
                try:
                    date = self._safe_date_conversion(record[field])
                    break
                except:
                    continue
        
        # 如果无法提取，使用当前日期
        if date is None:
            date = pd.Timestamp.now()
        
        return date
    
    def _extract_value(self, record):
        """
        从记录中提取值
        
        参数:
            record: 健康记录字典
            
        返回:
            提取的值或None（如果无法提取）
        """
        value = None
        
        # 尝试不同的值字段
        value_fields = ['value', 'Value', '值', '数值']
        for field in value_fields:
            if field in record and record[field]:
                try:
                    value = float(record[field])
                    break
                except:
                    value = record[field]
                    break
        
        return value
    
    def get_step_count_data(self):
        """
        获取步数数据
        
        返回:
            包含步数数据的DataFrame
        """
        try:
            # 步数相关的类型
            step_types = [
                'HKQuantityTypeIdentifierStepCount',
                'com.apple.health.type.quantity.steps',
                'StepCount'
            ]
            
            # 收集所有步数记录
            step_records = []
            for type_name in step_types:
                if type_name in self.record_types:
                    step_records.extend(self.record_types[type_name])
            
            if not step_records:
                return pd.DataFrame()
            
            # 提取每条记录的日期和步数值
            data = []
            for record in step_records:
                date = self._extract_date(record)
                value = self._extract_value(record)
                
                if date is not None and value is not None:
                    try:
                        value = float(value)
                        data.append({
                            'startDate': date,
                            'value': value
                        })
                    except:
                        continue
            
            if not data:
                return pd.DataFrame()
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 确保日期是datetime类型
            df['startDate'] = pd.to_datetime(df['startDate'])
            
            # 按日期排序
            df = df.sort_values('startDate')
            
            return df
        except Exception as e:
            print(f"Error getting step data: {str(e)}")
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_daily_step_count(self):
        """
        获取每日步数总和
        
        返回:
            包含每日步数的DataFrame
        """
        try:
            steps_data = self.get_step_count_data()
            if steps_data.empty:
                return pd.DataFrame()
            
            # 提取日期部分
            steps_data['日期'] = steps_data['startDate'].dt.date
            
            # 按日期分组并求和
            daily_steps = steps_data.groupby('日期')['value'].sum().reset_index()
            
            # 重命名列
            daily_steps.columns = ['日期', '步数']
            
            # 转换日期为字符串，便于JSON序列化
            daily_steps['日期'] = daily_steps['日期'].astype(str)
            
            return daily_steps
        except Exception as e:
            print(f"Error getting daily steps: {str(e)}")
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_heart_rate_data(self):
        """
        获取心率数据
        
        返回:
            包含心率数据的DataFrame
        """
        try:
            # 心率相关的类型
            hr_types = [
                'HKQuantityTypeIdentifierHeartRate',
                'com.apple.health.type.quantity.heartrate',
                'HeartRate'
            ]
            
            # 收集所有心率记录
            hr_records = []
            for type_name in hr_types:
                if type_name in self.record_types:
                    hr_records.extend(self.record_types[type_name])
            
            if not hr_records:
                return pd.DataFrame()
            
            # 提取每条记录的日期和心率值
            data = []
            for record in hr_records:
                date = self._extract_date(record)
                value = self._extract_value(record)
                
                if date is not None and value is not None:
                    try:
                        value = float(value)
                        data.append({
                            'startDate': date,
                            'value': value
                        })
                    except:
                        continue
            
            if not data:
                return pd.DataFrame()
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 确保日期是datetime类型
            df['startDate'] = pd.to_datetime(df['startDate'])
            
            # 按日期排序
            df = df.sort_values('startDate')
            
            return df
        except Exception as e:
            print(f"Error getting heart rate data: {str(e)}")
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_heart_rate_stats(self):
        """
        获取心率统计信息
        
        返回:
            包含心率统计的字典
        """
        try:
            hr_data = self.get_heart_rate_data()
            if hr_data.empty:
                return None
            
            hr_data['value'] = pd.to_numeric(hr_data['value'], errors='coerce')
            
            # 计算统计值
            avg_hr = hr_data['value'].mean()
            max_hr = hr_data['value'].max()
            min_hr = hr_data['value'].min()
            
            # 返回统计数据
            return {
                '平均心率': avg_hr,
                '最高心率': max_hr,
                '最低心率': min_hr
            }
        except Exception as e:
            print(f"Error getting heart rate stats: {str(e)}")
            traceback.print_exc()
            return None
    
    def get_sleep_analysis_data(self):
        """
        获取睡眠分析数据
        
        返回:
            包含睡眠数据的DataFrame
        """
        try:
            # 睡眠相关的类型
            sleep_types = [
                'HKCategoryTypeIdentifierSleepAnalysis',
                'com.apple.health.type.category.sleep',
                'SleepAnalysis'
            ]
            
            # 收集所有睡眠记录
            sleep_records = []
            for type_name in sleep_types:
                if type_name in self.record_types:
                    sleep_records.extend(self.record_types[type_name])
            
            if not sleep_records:
                return pd.DataFrame()
            
            # 提取每条记录的日期、持续时间和睡眠状态
            data = []
            for record in sleep_records:
                start_date = self._extract_date(record)
                
                # 尝试获取结束日期
                end_date = None
                if 'endDate' in record and record['endDate']:
                    try:
                        end_date = self._safe_date_conversion(record['endDate'])
                    except:
                        pass
                
                # 如果没有结束日期，尝试使用其他字段
                if end_date is None and 'End' in record and record['End']:
                    try:
                        end_date = self._safe_date_conversion(record['End'])
                    except:
                        pass
                
                # 计算持续时间
                duration = None
                if end_date is not None:
                    duration = (end_date - start_date).total_seconds() / 3600  # 小时
                
                # 尝试获取睡眠状态
                value = None
                if 'value' in record and record['value']:
                    value = record['value']
                elif 'Value' in record and record['Value']:
                    value = record['Value']
                
                if start_date is not None and (duration is not None or value is not None):
                    data.append({
                        'startDate': start_date,
                        'endDate': end_date,
                        'duration': duration,
                        'value': value
                    })
            
            if not data:
                return pd.DataFrame()
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 确保日期是datetime类型
            df['startDate'] = pd.to_datetime(df['startDate'])
            if 'endDate' in df.columns:
                df['endDate'] = pd.to_datetime(df['endDate'])
            
            # 按开始日期排序
            df = df.sort_values('startDate')
            
            return df
        except Exception as e:
            print(f"Error getting sleep data: {str(e)}")
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_sleep_duration_daily(self):
        """
        获取每日睡眠时长
        
        返回:
            包含每日睡眠时长的DataFrame
        """
        try:
            sleep_data = self.get_sleep_analysis_data()
            if sleep_data.empty:
                return pd.DataFrame()
            
            # 仅保留入睡状态的记录（如果有状态信息）
            if 'value' in sleep_data.columns:
                # 尝试过滤睡眠状态
                try:
                    sleep_states = ['asleep', 'inBed', '入睡', '睡眠']
                    mask = sleep_data['value'].str.lower().isin([state.lower() for state in sleep_states])
                    filtered_sleep_data = sleep_data[mask]
                    
                    # 如果过滤后没有数据，则使用所有数据
                    if filtered_sleep_data.empty:
                        filtered_sleep_data = sleep_data
                except:
                    filtered_sleep_data = sleep_data
            else:
                filtered_sleep_data = sleep_data
            
            # 提取日期部分
            filtered_sleep_data['日期'] = filtered_sleep_data['startDate'].dt.date
            
            # 按日期分组并计算总睡眠时长
            if 'duration' in filtered_sleep_data.columns and not filtered_sleep_data['duration'].isna().all():
                # 如果有持续时间列，直接使用
                daily_sleep = filtered_sleep_data.groupby('日期')['duration'].sum().reset_index()
            else:
                # 否则，尝试使用开始和结束时间计算
                if 'endDate' in filtered_sleep_data.columns:
                    filtered_sleep_data['duration'] = (
                        filtered_sleep_data['endDate'] - filtered_sleep_data['startDate']
                    ).dt.total_seconds() / 3600  # 小时
                    daily_sleep = filtered_sleep_data.groupby('日期')['duration'].sum().reset_index()
                else:
                    return pd.DataFrame()
            
            # 重命名列
            daily_sleep.columns = ['日期', '睡眠时长(小时)']
            
            # 转换日期为字符串，便于JSON序列化
            daily_sleep['日期'] = daily_sleep['日期'].astype(str)
            
            return daily_sleep
        except Exception as e:
            print(f"Error getting daily sleep duration: {str(e)}")
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_stress_indicators(self):
        """
        获取压力指标数据
        
        返回:
            包含压力指标的DataFrame
        """
        try:
            # 获取心率变异性数据
            hr_data = self.get_heart_rate_data()
            if hr_data.empty:
                # 返回包含必要列的空DataFrame
                return pd.DataFrame(columns=['日期', '心率波动', '心率范围', '平均心率', '压力指数', 'startDate'])
            
            # 确保数值类型
            hr_data['value'] = pd.to_numeric(hr_data['value'], errors='coerce')
            # 过滤掉NaN值
            hr_data = hr_data.dropna(subset=['value'])
            
            if hr_data.empty:
                # 返回包含必要列的空DataFrame
                return pd.DataFrame(columns=['日期', '心率波动', '心率范围', '平均心率', '压力指数', 'startDate'])
            
            # 提取日期部分
            hr_data['日期'] = hr_data['startDate'].dt.date
            
            # 计算每天的心率标准差和范围作为压力指标
            stress_data = hr_data.groupby('日期').agg(
                心率波动=('value', 'std'),
                心率范围=('value', lambda x: x.max() - x.min()),
                平均心率=('value', 'mean')
            ).reset_index()
            
            # 填充可能的NaN值
            stress_data = stress_data.fillna(0)
            
            # 确保所有数值列是float类型
            for col in ['心率波动', '心率范围', '平均心率']:
                stress_data[col] = pd.to_numeric(stress_data[col], errors='coerce').fillna(0).astype(float)
            
            # 计算压力指数（标准差和心率范围的综合指标）
            stress_data['压力指数'] = (
                stress_data['心率波动'] * 0.6 + stress_data['心率范围'] * 0.4
            ) / 10.0
            
            # 确保压力指数是float类型
            stress_data['压力指数'] = pd.to_numeric(stress_data['压力指数'], errors='coerce').fillna(0).astype(float)
            
            # 确保压力指数在1-10范围内
            stress_data['压力指数'] = np.clip(stress_data['压力指数'], 1, 10)
            
            # 存储日期原始值
            stress_data['startDate'] = stress_data['日期']
            
            # 转换日期为字符串，便于JSON序列化
            stress_data['日期'] = stress_data['日期'].astype(str)
            
            # 按日期排序
            stress_data = stress_data.sort_values('日期')
            
            # 最终再次确认所有数值列是float类型
            for col in ['心率波动', '心率范围', '平均心率', '压力指数']:
                stress_data[col] = pd.to_numeric(stress_data[col], errors='coerce').fillna(0).astype(float)
            
            return stress_data
        except Exception as e:
            print(f"Error getting stress indicators: {str(e)}")
            traceback.print_exc()
            # 返回包含必要列的空DataFrame
            return pd.DataFrame(columns=['日期', '心率波动', '心率范围', '平均心率', '压力指数', 'startDate'])
    
