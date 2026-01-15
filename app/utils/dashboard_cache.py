import glob
import os
import pickle

CACHE_FILENAME = "dashboard_cache.pkl"
CACHE_VERSION = 1


def _cache_path_for_source(source_path):
    if os.path.isdir(source_path):
        return os.path.join(source_path, CACHE_FILENAME)
    return os.path.join(os.path.dirname(source_path), CACHE_FILENAME)


def _get_source_stamp(source_path):
    try:
        if os.path.isdir(source_path):
            xml_files = glob.glob(
                os.path.join(source_path, "**", "export.xml"),
                recursive=True
            )
            if xml_files:
                return _get_source_stamp(xml_files[0])
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


def load_dashboard_cache(source_path):
    cache_path = _cache_path_for_source(source_path)
    if not os.path.exists(cache_path):
        return None

    source_stamp = _get_source_stamp(source_path)
    if not source_stamp:
        return None

    try:
        with open(cache_path, "rb") as cache_file:
            payload = pickle.load(cache_file)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    if payload.get("cache_version") != CACHE_VERSION:
        return None

    if payload.get("source_stamp") != source_stamp:
        return None

    return payload


def save_dashboard_cache(source_path, stats, dashboard_chart, data_types):
    source_stamp = _get_source_stamp(source_path)
    if not source_stamp:
        return False

    cache_path = _cache_path_for_source(source_path)
    payload = {
        "cache_version": CACHE_VERSION,
        "source_stamp": source_stamp,
        "stats": stats,
        "dashboard_chart": dashboard_chart,
        "data_types": data_types,
    }

    tmp_path = f"{cache_path}.tmp"
    try:
        with open(tmp_path, "wb") as cache_file:
            pickle.dump(payload, cache_file, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp_path, cache_path)
        return True
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False
