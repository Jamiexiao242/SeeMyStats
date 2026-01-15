from app import create_app
import sys

app = create_app()

if __name__ == '__main__':
    port = 5000
    # 检查是否指定了端口
    if len(sys.argv) > 1 and '--port' in sys.argv:
        port_index = sys.argv.index('--port') + 1
        if port_index < len(sys.argv):
            try:
                port = int(sys.argv[port_index])
            except ValueError:
                print(f"指定的端口无效: {sys.argv[port_index]}")
    
    app.run(debug=True, host='localhost', port=port) 