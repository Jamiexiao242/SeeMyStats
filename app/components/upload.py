import os
import threading
from flask import (
    Blueprint, flash, g, redirect, render_template, request, 
    session, url_for, current_app, jsonify
)
from werkzeug.utils import secure_filename
import uuid
from app.utils.health_parser import HealthDataParser
from app.components.dashboard import build_dashboard_payload
from app.utils.dashboard_cache import save_dashboard_cache

bp = Blueprint('upload', __name__, url_prefix='/upload')

# In-memory status tracking for background parsing.
UPLOAD_STATUS = {}
UPLOAD_LOCK = threading.Lock()

# Allowed file types
ALLOWED_EXTENSIONS = {'xml'}

def allowed_file(filename):
    """Check whether the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _set_upload_status(upload_id, status, message, progress):
    with UPLOAD_LOCK:
        UPLOAD_STATUS[upload_id] = {
            'status': status,
            'message': message,
            'progress': progress,
        }

def _parse_in_background(upload_id, file_path):
    def progress_callback(progress, message):
        _set_upload_status(upload_id, 'processing', message, progress)

    _set_upload_status(upload_id, 'processing', 'Parsing export.xml...', 5)
    parser = HealthDataParser()
    try:
        success = parser.parse_xml(file_path, progress_callback=progress_callback)
        if success:
            _set_upload_status(upload_id, 'processing', 'Building dashboard...', 97)
            stats, dashboard_chart, data_types = build_dashboard_payload(parser)
            cache_saved = save_dashboard_cache(
                file_path,
                stats,
                dashboard_chart,
                data_types
            )
            if not cache_saved:
                _set_upload_status(
                    upload_id,
                    'error',
                    'Failed to save dashboard cache.',
                    100
                )
                return
            _set_upload_status(upload_id, 'done', 'Parsing complete.', 100)
        else:
            _set_upload_status(upload_id, 'error', 'Failed to parse export.xml.', 100)
    except Exception as exc:
        _set_upload_status(upload_id, 'error', f'Parsing failed: {str(exc)}', 100)
    finally:
        parser.clean_up()

@bp.route('/status', methods=('GET',))
def status():
    upload_id = request.args.get('upload_id')
    if not upload_id:
        return jsonify({'status': 'unknown', 'message': 'Missing upload_id.', 'progress': 0}), 400

    with UPLOAD_LOCK:
        status_info = UPLOAD_STATUS.get(upload_id)

    if not status_info:
        return jsonify({'status': 'unknown', 'message': 'No active upload.', 'progress': 0}), 404

    return jsonify(status_info)

@bp.route('', methods=('GET', 'POST'))
def upload_file():
    """处理数据文件上传"""
    if request.method == 'POST':
        # 创建一个唯一的上传目录
        unique_id = uuid.uuid4()
        upload_id = str(unique_id)
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{unique_id}")
        os.makedirs(upload_dir, exist_ok=True)
        
        # 检查文件上传
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            
            if allowed_file(file.filename):
                # 保存文件
                filename = secure_filename(file.filename)
                if filename.lower() != 'export.xml':
                    flash('Only export.xml is supported.')
                    return redirect(request.url)

                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                
                # 处理文件
                # Store path for later use; parsing happens in the background.
                session['data_file_path'] = file_path
                session.pop('data_dir_path', None)

                _set_upload_status(upload_id, 'queued', 'Queued for parsing...', 5)
                thread = threading.Thread(
                    target=_parse_in_background,
                    args=(upload_id, file_path),
                    daemon=True
                )
                thread.start()
                return render_template('processing.html', upload_id=upload_id)
            else:
                flash(f'Unsupported file type: {file.filename}')
        else:
            flash('No file selected.')
        
        return redirect(request.url)
    
    return render_template('upload.html') 
